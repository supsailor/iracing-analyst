from __future__ import annotations

from pathlib import Path

import numpy as np

from .models import TelemetryRun


def synthetic_run(laps: int = 6, samples_per_lap: int = 1200) -> TelemetryRun:
    rng = np.random.default_rng(42)
    all_samples: dict[str, list[np.ndarray]] = {}
    session_offset = 0.0
    corners = [(0.12, 0.18, 25), (0.34, 0.42, 35), (0.61, 0.68, 22), (0.82, 0.9, 40)]
    for lap in range(1, laps + 1):
        dist = np.linspace(0, 1, samples_per_lap, endpoint=False)
        angle = dist * 2 * np.pi
        map_x = 900 * np.cos(angle) + 180 * np.cos(3 * angle)
        map_y = 520 * np.sin(angle) + 130 * np.sin(2 * angle)
        speed = np.full(samples_per_lap, 62.0)
        steering = np.zeros(samples_per_lap)
        yaw_rate = np.zeros(samples_per_lap)
        lat_accel = np.zeros(samples_per_lap)
        brake = np.zeros(samples_per_lap)
        throttle = np.ones(samples_per_lap)
        for ci, (start, end, drop) in enumerate(corners):
            center, width = (start + end) / 2, (end - start) / 2
            shape = np.exp(-0.5 * ((dist - center) / (width / 2)) ** 2)
            error = (lap - 3) * (0.7 if ci == 1 else 0.25)
            speed -= (drop + error) * shape
            steering += (0.18 + ci * 0.03) * shape * (-1 if ci % 2 else 1)
            yaw_rate += steering * 0.9
            lat_accel += steering * speed * 0.12
            brake += np.exp(-0.5 * ((dist - start) / 0.012) ** 2) * 0.82
            throttle -= np.clip(shape * 1.25, 0, 1)
        speed += rng.normal(0, 0.06, samples_per_lap)
        dt = (1 / samples_per_lap) / np.maximum(speed, 1) * 5200
        elapsed = np.cumsum(dt)
        elapsed -= elapsed[0]
        session_time = session_offset + elapsed
        session_offset = float(session_time[-1] + dt[-1])
        data = {
            "session_time": session_time, "lap": np.full(samples_per_lap, lap), "lap_dist_pct": dist,
            "speed": speed, "throttle": np.clip(throttle, 0, 1), "brake": np.clip(brake, 0, 1),
            "steering": steering, "gear": np.where(speed > 45, 5, 3), "rpm": speed * 110,
            "long_accel": np.gradient(speed) * 60, "lat_accel": lat_accel, "yaw": np.cumsum(yaw_rate) / 60,
            "yaw_rate": yaw_rate, "on_pit_road": np.zeros(samples_per_lap),
            "track_surface": np.full(samples_per_lap, 3), "incidents": np.zeros(samples_per_lap),
            "session_num": np.zeros(samples_per_lap), "session_state": np.full(samples_per_lap, 4),
            "session_unique_id": np.full(samples_per_lap, 4242),
            "session_tick": np.arange((lap - 1) * samples_per_lap, lap * samples_per_lap),
            "is_on_track_car": np.ones(samples_per_lap), "enter_exit_reset": np.full(samples_per_lap, 2),
            "latitude": 50.0 + map_y / 110_540, "longitude": 5.0 + map_x / (111_320 * np.cos(np.radians(50))),
            "altitude": np.full(samples_per_lap, 400), "yaw_north": np.unwrap(np.arctan2(np.gradient(map_y), np.gradient(map_x))),
            "velocity_x": np.gradient(map_x) / np.maximum(dt, 1e-4),
            "velocity_y": np.gradient(map_y) / np.maximum(dt, 1e-4),
        }
        for key, values in data.items():
            all_samples.setdefault(key, []).append(np.asarray(values))
    return TelemetryRun(
        samples={key: np.concatenate(values) for key, values in all_samples.items()},
        metadata={
            "source": "fixture", "track": "Synthetic Road Course", "car": "Synthetic GT",
            "session_type": "Practice", "session_num": 0, "subsession_id": 4242,
            "session_key": "4242:0:0", "layout": "Full Course", "official_turns": 4,
            "track_length": "5.2 km",
        },
    )


def write_fixture(path: Path) -> None:
    run = synthetic_run()
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {key: np.asarray(value) for key, value in run.samples.items()}
    arrays.update({f"meta_{key}": np.array(str(value)) for key, value in run.metadata.items()})
    np.savez_compressed(path, **arrays)


def spa_demo_run() -> TelemetryRun:
    """Return anonymous, deterministic demonstration data shaped like a Spa-style road layout."""
    run = synthetic_run()
    control = np.array([
        [0, 0], [-120, 70], [-180, 210], [-120, 330], [80, 370], [300, 345],
        [540, 300], [760, 200], [930, 80], [890, -90], [690, -120], [500, -40],
        [350, -150], [190, -280], [5, -250], [-95, -125], [-35, -30], [0, 0],
    ], dtype=float)
    edge = np.linalg.norm(np.diff(control, axis=0), axis=1)
    distance = np.concatenate(([0.0], np.cumsum(edge)))
    distance /= distance[-1]
    lap_distance = np.asarray(run.samples["lap_dist_pct"], dtype=float)
    map_x = np.interp(lap_distance, distance, control[:, 0])
    map_y = np.interp(lap_distance, distance, control[:, 1])
    phase = lap_distance * 2 * np.pi
    map_x += 18 * np.sin(phase * 3)
    map_y += 12 * np.sin(phase * 2)
    latitude = 50.4372 + map_y / 110_540
    longitude = 5.9714 + map_x / (111_320 * np.cos(np.radians(50.4372)))
    run.samples["latitude"] = latitude
    run.samples["longitude"] = longitude
    speed = np.asarray(run.samples["speed"], dtype=float).copy()
    lap_number = np.asarray(run.samples["lap"], dtype=int)
    specialists = {2: (0.37, 0.12), 4: (0.65, 0.22), 5: (0.94, 0.52)}
    for number, (strong_at, penalty_at) in specialists.items():
        mask = lap_number == number
        local = lap_distance[mask]
        speed[mask] += 4.5 * np.exp(-0.5 * ((local - strong_at) / 0.025) ** 2)
        speed[mask] -= 7.0 * np.exp(-0.5 * ((local - penalty_at) / 0.02) ** 2)
    run.samples["speed"] = speed
    session_time = np.empty_like(speed)
    offset = 0.0
    for number in sorted(set(lap_number.tolist())):
        mask = lap_number == number
        local_speed = np.maximum(speed[mask], 1)
        dt = (1 / mask.sum()) / local_speed * 5200
        elapsed = np.cumsum(dt)
        elapsed -= elapsed[0]
        session_time[mask] = offset + elapsed
        offset = float(session_time[mask][-1] + dt[-1])
    run.samples["session_time"] = session_time
    run.metadata.update({
        "track": "Circuit de Spa-Francorchamps", "track_name": "spa",
        "layout": "Grand Prix", "official_turns": 19, "track_length": "7.004 km",
        "car": "Porsche 911 GT3 Cup (992)", "source": "fixture",
    })
    return run


def write_spa_demo(path: Path) -> None:
    run = spa_demo_run()
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {key: np.asarray(value) for key, value in run.samples.items()}
    arrays.update({f"meta_{key}": np.array(str(value)) for key, value in run.metadata.items()})
    np.savez_compressed(path, **arrays)
