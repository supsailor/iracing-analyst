from __future__ import annotations

import re
import struct
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .models import CHANNELS, TelemetryRun


IRSDK_TYPES = {
    0: ("?", np.bool_), 1: ("i", np.int32), 2: ("I", np.uint32), 3: ("f", np.float32),
    4: ("d", np.float64), 5: ("c", np.byte),
}
VARIABLE_ALIASES = {
    "session_time": "SessionTime", "lap": "Lap", "lap_dist_pct": "LapDistPct",
    "speed": "Speed", "throttle": "Throttle", "brake": "Brake", "steering": "SteeringWheelAngle",
    "gear": "Gear", "rpm": "RPM", "long_accel": "LongAccel", "lat_accel": "LatAccel",
    "yaw": "Yaw", "yaw_rate": "YawRate", "on_pit_road": "OnPitRoad",
    "track_surface": "PlayerTrackSurface", "incidents": "PlayerCarMyIncidentCount",
    "session_num": "SessionNum", "session_state": "SessionState",
    "session_unique_id": "SessionUniqueID", "session_tick": "SessionTick",
    "is_on_track_car": "IsOnTrackCar", "enter_exit_reset": "EnterExitReset",
    "latitude": "Lat", "longitude": "Lon", "altitude": "Alt", "yaw_north": "YawNorth",
    "velocity_x": "VelocityX", "velocity_y": "VelocityY",
}


def _cstring(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")


class IbtReader:
    """Minimal, dependency-free reader for the documented iRacing disk telemetry layout."""

    def read(self, path: Path) -> TelemetryRun:
        raw = path.read_bytes()
        if len(raw) < 112:
            raise ValueError("File is too small to be an iRacing telemetry file")
        version, _, tick_rate, _, session_len, session_offset, num_vars, var_offset, num_buf, buf_len = struct.unpack_from("<10i", raw, 0)
        if version < 1 or num_vars <= 0 or buf_len <= 0 or num_buf <= 0:
            raise ValueError("Unsupported or corrupt iRacing telemetry header")
        buffer_offset = struct.unpack_from("<i", raw, 52)[0]
        if buffer_offset <= 0:
            raise ValueError("Telemetry data buffer is missing")
        variables: dict[str, tuple[int, int, int]] = {}
        for index in range(num_vars):
            pos = var_offset + index * 144
            var_type, offset, count = struct.unpack_from("<3i", raw, pos)
            name = _cstring(raw[pos + 16:pos + 48])
            variables[name] = (var_type, offset, count)
        row_count = max(0, (len(raw) - buffer_offset) // buf_len)
        samples: dict[str, np.ndarray] = {}
        for target, source in VARIABLE_ALIASES.items():
            if source not in variables:
                continue
            var_type, offset, count = variables[source]
            if count != 1 or var_type not in IRSDK_TYPES:
                continue
            fmt, dtype = IRSDK_TYPES[var_type]
            values = np.empty(row_count, dtype=dtype)
            size = struct.calcsize("<" + fmt)
            for row in range(row_count):
                position = buffer_offset + row * buf_len + offset
                if position + size > len(raw):
                    values = values[:row]
                    break
                values[row] = struct.unpack_from("<" + fmt, raw, position)[0]
            samples[target] = values
        if "session_time" not in samples or "lap_dist_pct" not in samples:
            raise ValueError("IBT does not contain required SessionTime/LapDistPct variables")
        length = len(samples["session_time"])
        for channel in CHANNELS:
            default = 3.0 if channel == "track_surface" else 0.0
            samples.setdefault(channel, np.full(length, default, dtype=float))
        session = _cstring(raw[session_offset:session_offset + session_len]) if session_len else ""
        def yaml_value(key: str, fallback: str) -> str:
            match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", session, re.MULTILINE)
            return match.group(1).strip('"') if match else fallback
        metadata = {
            "source": "ibt", "tick_rate": tick_rate, "track": yaml_value("TrackDisplayName", path.stem),
            "car": yaml_value("CarScreenName", "Unknown car"), "original_path": str(path),
            "track_name": yaml_value("TrackName", ""), "layout": yaml_value("TrackConfigName", ""),
            "track_id": yaml_value("TrackID", ""), "official_turns": yaml_value("TrackNumTurns", ""),
            "track_length": yaml_value("TrackLength", ""), "track_north_offset": yaml_value("TrackNorthOffset", ""),
            "subsession_id": yaml_value("SubSessionID", ""),
        }
        if "session_num" in samples and len(samples["session_num"]):
            session_num = int(samples["session_num"][0])
            metadata["session_num"] = session_num
            session_pattern = rf"-\s*SessionNum:\s*{session_num}.*?SessionType:\s*(.+?)\s*$"
            session_match = re.search(session_pattern, session, re.MULTILINE | re.DOTALL)
            metadata["session_type"] = session_match.group(1).strip() if session_match else "Session"
        metadata["session_key"] = ":".join(str(metadata.get(key, "")) for key in (
            "subsession_id", "session_num", "car",
        ))
        return TelemetryRun(samples=samples, metadata=metadata)


def read_npz(path: Path) -> TelemetryRun:
    with np.load(path, allow_pickle=False) as data:
        samples = {key: data[key] for key in data.files if not key.startswith("meta_")}
        metadata = {key[5:]: str(data[key].item()) for key in data.files if key.startswith("meta_")}
    return TelemetryRun(samples=samples, metadata=metadata)


class LiveCollector:
    def __init__(self, on_complete: Callable[[TelemetryRun], None]):
        self.on_complete = on_complete
        self.connected = False
        self.recording = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="iracing-live-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        if sys.platform != "win32":
            return
        import irsdk  # type: ignore
        sdk = irsdk.IRSDK()
        collected: dict[str, list] = {key: [] for key in CHANNELS}
        metadata: dict[str, object] = {"source": "live"}
        finalized = False
        active_key: str | None = None
        disconnected_at: float | None = None

        def flush() -> None:
            nonlocal collected
            if collected["session_time"]:
                self.on_complete(TelemetryRun(
                    samples={key: np.asarray(values) for key, values in collected.items()},
                    metadata=dict(metadata),
                ))
            collected = {key: [] for key in CHANNELS}

        while not self._stop.is_set():
            available = bool(sdk.startup())
            self.connected = available
            if not available:
                if disconnected_at is None:
                    disconnected_at = time.monotonic()
                if time.monotonic() - disconnected_at >= 15 and collected["session_time"]:
                    self.recording = False
                    flush()
                finalized = False
                time.sleep(1.0)
                continue
            disconnected_at = None
            session_state = sdk["SessionState"]
            session_num = sdk["SessionNum"]
            session_unique_id = sdk["SessionUniqueID"]
            weekend = sdk["WeekendInfo"] or {}
            driver = sdk["DriverInfo"] or {}
            driver_index = int(driver.get("DriverCarIdx", 0) or 0)
            subsession_id = weekend.get("SubSessionID", session_unique_id)
            current_key = f"{subsession_id}:{session_num}:{driver_index}"
            if active_key is not None and current_key != active_key:
                flush()
                finalized = False
            active_key = current_key
            sessions = (sdk["SessionInfo"] or {}).get("Sessions", [])
            current_session = next((item for item in sessions if item.get("SessionNum") == session_num), {})
            drivers = driver.get("Drivers", [{}])
            car = drivers[driver_index].get("CarScreenName", "Unknown car") if driver_index < len(drivers) else "Unknown car"
            metadata.update({
                "session_key": current_key, "subsession_id": subsession_id,
                "session_unique_id": session_unique_id, "session_num": session_num,
                "session_type": current_session.get("SessionType", "Session"), "driver_car_idx": driver_index,
                "track": weekend.get("TrackDisplayName", "Unknown track"),
                "track_name": weekend.get("TrackName", ""), "layout": weekend.get("TrackConfigName", ""),
                "track_id": weekend.get("TrackID", ""), "official_turns": weekend.get("TrackNumTurns", ""),
                "track_length": weekend.get("TrackLength", ""), "track_north_offset": weekend.get("TrackNorthOffset", ""),
                "car": car,
            })
            checkered = isinstance(session_state, int) and session_state >= 5
            if finalized and not checkered:
                finalized = False
            if checkered and self.recording and collected["session_time"]:
                self.recording = False
                flush()
                finalized = True
            if checkered or finalized:
                time.sleep(0.25)
                continue
            on_track = sdk["IsOnTrackCar"]
            self.recording = bool(on_track)
            if not on_track:
                time.sleep(0.1)
                continue
            try:
                sdk.freeze_var_buffer_latest()
                for target, source in VARIABLE_ALIASES.items():
                    value = sdk[source]
                    collected[target].append(0 if value is None else value)
            except (AttributeError, IndexError, TypeError):
                pass
            finally:
                sdk.unfreeze_var_buffer_latest()
            time.sleep(1 / 60)
        flush()
        sdk.shutdown()
