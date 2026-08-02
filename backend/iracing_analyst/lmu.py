from __future__ import annotations

import ctypes
import hashlib
import mmap
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import duckdb
import numpy as np

from .models import CHANNELS, TelemetryRun
from .vendor.lmu_data import LMUConstants, LMUObjectOut


SAMPLED_CHANNELS = {
    "speed": ("Ground Speed", 1 / 3.6),
    "throttle": ("Throttle Pos", 0.01),
    "brake": ("Brake Pos", 0.01),
    "clutch": ("Clutch Pos", 0.01),
    "steering": ("Steering Pos", 0.01),
    "rpm": ("Engine RPM", 1.0),
    "latitude": ("GPS Latitude", 1.0),
    "longitude": ("GPS Longitude", 1.0),
    "yaw_rate": ("Yaw Rate", 1.0),
}
EVENT_CHANNELS = {
    "lap": "Lap",
    "gear": "Gear",
    "on_pit_road": "In Pits",
    "lap_invalidated": "Lap Invalidated",
    "track_limits": "Track Limits Steps",
}
SESSION_TYPES = {
    0: "Test Day",
    1: "Practice 1", 2: "Practice 2", 3: "Practice 3", 4: "Practice 4",
    5: "Qualifying 1", 6: "Qualifying 2", 7: "Qualifying 3", 8: "Qualifying 4",
    9: "Warmup",
    10: "Race 1", 11: "Race 2", 12: "Race 3", 13: "Race 4",
}


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _decode(value: bytes) -> str:
    return value.split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


class LmuDuckDbReader:
    """Read LMU's native DuckDB telemetry export into the canonical model."""

    def read(self, path: Path) -> TelemetryRun:
        path = Path(path)
        try:
            connection = duckdb.connect(str(path), read_only=True)
        except duckdb.Error as exc:
            raise ValueError(f"Cannot open LMU telemetry database: {exc}") from exc
        try:
            tables = {row[0] for row in connection.execute("SHOW TABLES").fetchall()}
            required = {"metadata", "channelsList", "eventsList", "GPS Time", "Lap", "Lap Dist"}
            missing = sorted(required - tables)
            if missing:
                raise ValueError("Unsupported LMU telemetry schema; missing: " + ", ".join(missing))
            metadata = dict(connection.execute(
                'SELECT CAST(key AS VARCHAR), CAST(value AS VARCHAR) FROM "metadata"',
            ).fetchall())
            frequencies = {
                str(name): float(frequency)
                for name, frequency in connection.execute(
                    'SELECT channelName, frequency FROM "channelsList"',
                ).fetchall()
                if frequency and float(frequency) > 0
            }
            master = self._column(connection, "GPS Time")
            if master.size < 2 or np.any(np.diff(master) <= 0):
                raise ValueError("LMU GPS Time channel is missing or non-monotonic")
            start, end = float(master[0]), float(master[-1])
            samples = {key: np.zeros(master.size, dtype=float) for key in CHANNELS}
            samples["session_time"] = master - start
            samples["sample_sequence"] = np.arange(master.size, dtype=float)
            samples["capture_epoch"] = np.zeros(master.size, dtype=float)
            samples["session_state"] = np.full(master.size, 5.0)
            samples["is_on_track_car"] = np.ones(master.size, dtype=float)
            samples["track_surface"] = np.full(master.size, 3.0)
            for target, (source, scale) in SAMPLED_CHANNELS.items():
                if source in tables and source in frequencies:
                    samples[target] = self._sampled(
                        connection, source, frequencies[source], master, start, end,
                    ) * scale
            lap_distance = self._sampled(
                connection, "Lap Dist", frequencies.get("Lap Dist", 10.0), master, start, end,
                step=True,
            )
            for target, source in EVENT_CHANNELS.items():
                if source in tables:
                    samples[target] = self._events(connection, source, master)
            samples["on_pit_road"] = samples["on_pit_road"] > 0
            samples["long_accel"] = self._acceleration(
                connection, tables, frequencies, master, start, end,
                "Longitudinal Acceleration", "G Force Long",
            )
            samples["lat_accel"] = self._acceleration(
                connection, tables, frequencies, master, start, end,
                "Lateral Acceleration", "G Force Lat",
            )
            track_length = self._track_length(samples["lap"], lap_distance)
            if not np.isfinite(track_length) or track_length < 100:
                raise ValueError("LMU telemetry does not contain a plausible track length")
            samples["lap"] = self._align_lap_events(
                samples["lap"], lap_distance, master, track_length,
            )
            samples["lap_dist_pct"] = np.clip(lap_distance / track_length, 0, 1)
            fingerprint = _sha256(path)
            run_metadata = {
                "source": "duckdb",
                "capture_source": "duckdb",
                "simulator": "lmu",
                "coordinate_system": "gps",
                "source_fingerprint": fingerprint,
                "original_path": str(path),
                "original_name": path.name,
                "track": metadata.get("TrackName", path.stem),
                "track_name": metadata.get("TrackName", ""),
                "layout": metadata.get("TrackLayout", ""),
                "car": metadata.get("CarName", "Unknown car"),
                "session_type": metadata.get("SessionType", "Session"),
                "recording_time": metadata.get("RecordingTime", ""),
                "driver_name": metadata.get("DriverName", ""),
                "track_length": f"{track_length:.1f} m",
                "session_key": "lmu-duckdb:" + fingerprint,
                "schema_version": metadata.get("Version", "1"),
                "steering_unit": "normalized",
            }
            return TelemetryRun(samples=samples, metadata=run_metadata)
        except duckdb.Error as exc:
            raise ValueError(f"Cannot read LMU telemetry database: {exc}") from exc
        finally:
            connection.close()

    @staticmethod
    def _column(connection: duckdb.DuckDBPyConnection, table: str) -> np.ndarray:
        rows = connection.execute(f"SELECT value FROM {_quote(table)}").fetchnumpy()
        return np.asarray(rows["value"], dtype=float)

    def _sampled(
        self,
        connection: duckdb.DuckDBPyConnection,
        table: str,
        frequency: float,
        master: np.ndarray,
        start: float,
        end: float,
        step: bool = False,
    ) -> np.ndarray:
        values = self._column(connection, table)
        if not values.size:
            return np.zeros(master.size, dtype=float)
        timeline = start + np.arange(values.size, dtype=float) / frequency
        usable = timeline <= end + 1 / frequency
        if step:
            positions = np.searchsorted(timeline[usable], master, side="right") - 1
            positions = np.clip(positions, 0, np.count_nonzero(usable) - 1)
            return values[usable][positions]
        return np.interp(master, timeline[usable], values[usable])

    @staticmethod
    def _events(
        connection: duckdb.DuckDBPyConnection, table: str, master: np.ndarray,
    ) -> np.ndarray:
        rows = connection.execute(
            f"SELECT ts, value FROM {_quote(table)} ORDER BY ts",
        ).fetchnumpy()
        timestamps = np.asarray(rows["ts"], dtype=float)
        values = np.asarray(rows["value"], dtype=float)
        if not timestamps.size:
            return np.zeros(master.size, dtype=float)
        positions = np.searchsorted(timestamps, master, side="right") - 1
        output = np.zeros(master.size, dtype=float)
        available = positions >= 0
        output[available] = values[positions[available]]
        return output

    def _acceleration(
        self,
        connection: duckdb.DuckDBPyConnection,
        tables: set[str],
        frequencies: dict[str, float],
        master: np.ndarray,
        start: float,
        end: float,
        direct: str,
        g_force: str,
    ) -> np.ndarray:
        source = direct if direct in tables else g_force if g_force in tables else None
        if not source:
            return np.zeros(master.size, dtype=float)
        values = self._sampled(
            connection, source, frequencies.get(source, 10.0), master, start, end,
        )
        return values * 9.80665 if source == g_force else values

    @staticmethod
    def _track_length(laps: np.ndarray, distance: np.ndarray) -> float:
        maxima = []
        changes = np.flatnonzero(np.diff(laps) != 0) + 1
        for indices in np.split(np.arange(len(laps)), changes):
            if indices.size > 20:
                maxima.append(float(np.max(distance[indices])))
        if not maxima:
            return float(np.max(distance))
        upper = max(maxima)
        completed = [value for value in maxima if value >= upper * 0.9]
        return float(np.median(completed or maxima))

    @staticmethod
    def _align_lap_events(
        laps: np.ndarray, distance: np.ndarray, timeline: np.ndarray, track_length: float,
    ) -> np.ndarray:
        """Align asynchronous Lap events to the physical start/finish crossing."""
        changes = np.flatnonzero(np.diff(laps) != 0) + 1
        resets = np.flatnonzero(np.diff(distance) < -track_length * 0.5) + 1
        if not changes.size or not resets.size:
            return laps
        boundaries: list[tuple[int, float]] = []
        for change in changes:
            closest = int(resets[np.argmin(np.abs(timeline[resets] - timeline[change]))])
            boundary = closest if abs(timeline[closest] - timeline[change]) <= 2.0 else int(change)
            boundaries.append((boundary, float(laps[change])))
        aligned = np.full(laps.shape, float(laps[0]))
        current = float(laps[0])
        start = 0
        for boundary, next_lap in sorted(boundaries):
            aligned[start:boundary] = current
            current = next_lap
            start = boundary
        aligned[start:] = current
        return aligned


@dataclass(slots=True)
class LmuSnapshot:
    session_time: float
    session_number: int
    game_phase: int
    track: str
    track_length: float
    session_start: float
    player_id: int
    player_name: str
    steam_id: int
    car: str
    car_file: str
    lap: int
    lap_distance: float
    on_track: bool
    on_pit_road: bool
    in_garage: bool
    speed: float
    throttle: float
    brake: float
    clutch: float
    steering: float
    gear: int
    rpm: float
    long_accel: float
    lat_accel: float
    yaw_rate: float
    yaw_north: float
    position_x: float
    position_y: float
    altitude: float
    velocity_x: float
    velocity_y: float
    lap_invalidated: bool
    track_limits: int
    surface_type: int

    @property
    def session_type(self) -> str:
        return SESSION_TYPES.get(self.session_number, f"Session {self.session_number}")

    @property
    def session_key(self) -> str:
        driver = str(self.steam_id) if self.steam_id else self.player_name
        identity = f"{self.track}|{self.session_number}|{self.session_start:.3f}|{driver}|{self.car_file}"
        return "lmu-live:" + hashlib.sha256(identity.encode()).hexdigest()[:24]


class LmuSnapshotSource(Protocol):
    def open(self) -> None: ...
    def read(self) -> LmuSnapshot | None: ...
    def close(self) -> None: ...


class LmuSharedMemorySource:
    """Access LMU's built-in Windows shared memory using the official structure layout."""

    def __init__(self) -> None:
        self._mapping: mmap.mmap | None = None
        self._size = ctypes.sizeof(LMUObjectOut)

    def open(self) -> None:
        if sys.platform != "win32":
            raise OSError("LMU shared memory is available on Windows only")
        self._mapping = mmap.mmap(-1, self._size, LMUConstants.LMU_SHARED_MEMORY_FILE)

    def close(self) -> None:
        if self._mapping is not None:
            self._mapping.close()
            self._mapping = None

    def read(self) -> LmuSnapshot | None:
        if self._mapping is None:
            return None
        self._mapping.seek(0)
        return self.parse(self._mapping.read(self._size))

    @staticmethod
    def parse(raw: bytes) -> LmuSnapshot | None:
        if len(raw) < ctypes.sizeof(LMUObjectOut):
            return None
        data = LMUObjectOut.from_buffer_copy(raw)
        events = data.generic.events
        scoring_info = data.scoring.scoringInfo
        telemetry_data = data.telemetry
        if data.generic.gameVersion <= 0:
            return None
        if not (events.SME_UPDATE_SCORING or events.SME_UPDATE_TELEMETRY):
            return None
        scoring_count = min(int(scoring_info.mNumVehicles), LMUConstants.MAX_MAPPED_VEHICLES)
        telemetry_count = min(int(telemetry_data.activeVehicles), LMUConstants.MAX_MAPPED_VEHICLES)
        if scoring_count <= 0 or telemetry_count <= 0:
            return None
        player_score = next(
            (data.scoring.vehScoringInfo[index] for index in range(scoring_count)
             if data.scoring.vehScoringInfo[index].mIsPlayer),
            None,
        )
        if player_score is None:
            return None
        player_telemetry = next(
            (telemetry_data.telemInfo[index] for index in range(telemetry_count)
             if telemetry_data.telemInfo[index].mID == player_score.mID),
            None,
        )
        if player_telemetry is None:
            return None
        velocity = player_telemetry.mLocalVel
        acceleration = player_telemetry.mLocalAccel
        forward = player_telemetry.mOri[2]
        wheels = player_telemetry.mWheels
        surface_type = max(int(wheel.mSurfaceType) for wheel in wheels)
        return LmuSnapshot(
            session_time=float(player_telemetry.mElapsedTime),
            session_number=int(scoring_info.mSession),
            game_phase=int(scoring_info.mGamePhase),
            track=_decode(scoring_info.mTrackName) or _decode(player_telemetry.mTrackName),
            track_length=float(scoring_info.mLapDist),
            session_start=float(scoring_info.mStartET),
            player_id=int(player_score.mID),
            player_name=_decode(scoring_info.mPlayerName),
            steam_id=int(player_score.mSteamID),
            car=_decode(player_telemetry.mVehicleModel) or _decode(player_telemetry.mVehicleName),
            car_file=_decode(player_score.mVehFilename),
            lap=int(player_telemetry.mLapNumber),
            lap_distance=float(player_score.mLapDist),
            on_track=bool(
                scoring_info.mInRealtime
                and telemetry_data.playerHasVehicle
                and not player_score.mInGarageStall
            ),
            on_pit_road=bool(player_score.mInPits or 2 <= player_score.mPitState <= 4),
            in_garage=bool(player_score.mInGarageStall),
            speed=float(np.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)),
            throttle=float(player_telemetry.mFilteredThrottle),
            brake=float(player_telemetry.mFilteredBrake),
            clutch=float(player_telemetry.mFilteredClutch),
            steering=float(player_telemetry.mFilteredSteering),
            gear=int(player_telemetry.mGear),
            rpm=float(player_telemetry.mEngineRPM),
            long_accel=float(acceleration.z),
            lat_accel=float(acceleration.x),
            yaw_rate=float(player_telemetry.mLocalRot.y),
            yaw_north=float(np.arctan2(forward.x, forward.z)),
            position_x=float(player_telemetry.mPos.x),
            position_y=float(player_telemetry.mPos.z),
            altitude=float(player_telemetry.mPos.y),
            velocity_x=float(velocity.x),
            velocity_y=float(velocity.z),
            lap_invalidated=bool(player_telemetry.mLapInvalidated),
            track_limits=int(player_telemetry.mTrackLimitsSteps),
            surface_type=surface_type,
        )


class LmuRunBuilder:
    """State machine that combines LMU stints into one analytical session."""

    def __init__(self) -> None:
        self.samples: dict[str, list[float]] = {key: [] for key in CHANNELS}
        self.metadata: dict[str, object] = {}
        self.session_key: str | None = None
        self.capture_epoch = 0
        self.sample_sequence = 0
        self.last_session_time: float | None = None
        self.last_lap: int | None = None
        self.last_distance: float | None = None
        self.pending_reset = False
        self.recording = False

    def ingest(self, snapshot: LmuSnapshot) -> list[TelemetryRun]:
        completed: list[TelemetryRun] = []
        if self.session_key and snapshot.session_key != self.session_key:
            run = self.finish()
            if run:
                completed.append(run)
        self.session_key = snapshot.session_key
        self._update_metadata(snapshot)
        if snapshot.game_phase == 8:
            run = self.finish()
            if run:
                completed.append(run)
            return completed
        if not snapshot.on_track:
            if self.recording:
                self.pending_reset = True
            self.recording = False
            return completed
        reset = self.pending_reset
        if self.last_session_time is not None and snapshot.session_time < self.last_session_time - 0.5:
            reset = True
        if self.last_lap is not None and snapshot.lap < self.last_lap:
            reset = True
        if (
            self.last_distance is not None
            and snapshot.lap == self.last_lap
            and snapshot.lap_distance < self.last_distance - max(snapshot.track_length * 0.5, 100)
        ):
            reset = True
        if reset:
            self.capture_epoch += 1
            self.last_session_time = None
        self.pending_reset = False
        self.recording = True
        if self.last_session_time is not None and snapshot.session_time <= self.last_session_time:
            return completed
        self._append(snapshot, reset)
        self.last_session_time = snapshot.session_time
        self.last_lap = snapshot.lap
        self.last_distance = snapshot.lap_distance
        return completed

    def finish(self) -> TelemetryRun | None:
        if not self.samples["session_time"]:
            self._reset()
            return None
        run = TelemetryRun(
            samples={key: np.asarray(value) for key, value in self.samples.items()},
            metadata=dict(self.metadata),
        )
        self._reset()
        return run

    def _reset(self) -> None:
        self.samples = {key: [] for key in CHANNELS}
        self.metadata = {}
        self.session_key = None
        self.capture_epoch = 0
        self.last_session_time = None
        self.last_lap = None
        self.last_distance = None
        self.pending_reset = False
        self.recording = False

    def _update_metadata(self, snapshot: LmuSnapshot) -> None:
        self.metadata.update({
            "source": "live",
            "capture_source": "live",
            "simulator": "lmu",
            "coordinate_system": "world_xy",
            "session_key": snapshot.session_key,
            "session_num": snapshot.session_number,
            "session_type": snapshot.session_type,
            "track": snapshot.track or "Unknown LMU track",
            "track_name": snapshot.track,
            "layout": "",
            "track_length": f"{snapshot.track_length:.1f} m",
            "car": snapshot.car or "Unknown LMU car",
            "driver_name": snapshot.player_name,
            "driver_car_idx": snapshot.player_id,
            "steering_unit": "normalized",
        })

    def _append(self, snapshot: LmuSnapshot, reset: bool) -> None:
        track_length = max(snapshot.track_length, 1.0)
        values: dict[str, float] = {
            "session_time": snapshot.session_time,
            "lap": snapshot.lap,
            "lap_dist_pct": np.clip(snapshot.lap_distance / track_length, 0, 1),
            "speed": snapshot.speed,
            "throttle": snapshot.throttle,
            "brake": snapshot.brake,
            "clutch": snapshot.clutch,
            "steering": snapshot.steering,
            "gear": snapshot.gear,
            "rpm": snapshot.rpm,
            "long_accel": snapshot.long_accel,
            "lat_accel": snapshot.lat_accel,
            "yaw": snapshot.yaw_north,
            "yaw_rate": snapshot.yaw_rate,
            "on_pit_road": float(snapshot.on_pit_road),
            "track_surface": 0.0 if snapshot.surface_type in {2, 3, 4} else 3.0,
            "incidents": 0.0,
            "session_num": snapshot.session_number,
            "session_state": snapshot.game_phase,
            "session_unique_id": 0.0,
            "session_tick": round(snapshot.session_time * 1000),
            "is_on_track_car": 1.0,
            "enter_exit_reset": float(reset),
            "latitude": 0.0,
            "longitude": 0.0,
            "altitude": snapshot.altitude,
            "yaw_north": snapshot.yaw_north,
            "velocity_x": snapshot.velocity_x,
            "velocity_y": snapshot.velocity_y,
            "position_x": snapshot.position_x,
            "position_y": snapshot.position_y,
            "lap_invalidated": float(snapshot.lap_invalidated),
            "track_limits": snapshot.track_limits,
            "capture_epoch": self.capture_epoch,
            "sample_sequence": self.sample_sequence,
        }
        for key in CHANNELS:
            self.samples[key].append(float(values.get(key, 0.0)))
        self.sample_sequence += 1


class LmuLiveCollector:
    def __init__(
        self,
        on_complete: Callable[[TelemetryRun], None],
        source_factory: Callable[[], LmuSnapshotSource] = LmuSharedMemorySource,
        disconnect_debounce: float = 15.0,
    ):
        self.on_complete = on_complete
        self.source_factory = source_factory
        self.disconnect_debounce = disconnect_debounce
        self.connected = False
        self.recording = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="lmu-live-collector", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run(self) -> None:
        if sys.platform != "win32":
            return
        builder = LmuRunBuilder()
        source = self.source_factory()
        disconnected_at: float | None = None
        try:
            source.open()
            while not self._stop.is_set():
                snapshot = source.read()
                self.connected = snapshot is not None
                if snapshot is None:
                    self.recording = False
                    if disconnected_at is None:
                        disconnected_at = time.monotonic()
                    elif time.monotonic() - disconnected_at >= self.disconnect_debounce:
                        run = builder.finish()
                        if run:
                            self.on_complete(run)
                        disconnected_at = time.monotonic()
                    self._stop.wait(0.25)
                    continue
                disconnected_at = None
                for run in builder.ingest(snapshot):
                    self.on_complete(run)
                self.recording = builder.recording
                self._stop.wait(1 / 60)
        except OSError:
            self.connected = False
            self.recording = False
        finally:
            run = builder.finish()
            if run:
                self.on_complete(run)
            source.close()
