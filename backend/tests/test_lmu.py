from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import duckdb
import numpy as np
import pytest

from iracing_analyst.analysis import analyze
from iracing_analyst.lmu import (
    LmuDuckDbReader,
    LmuRunBuilder,
    LmuSharedMemorySource,
    LmuSnapshot,
)
from iracing_analyst.storage import SessionStore
from iracing_analyst.vendor.lmu_data import LMUObjectOut


def snapshot(**overrides) -> LmuSnapshot:
    base = LmuSnapshot(
        session_time=10.0,
        session_number=1,
        game_phase=5,
        track="Circuit de Test",
        track_length=5000.0,
        session_start=12345.0,
        player_id=7,
        player_name="Driver",
        steam_id=123,
        car="LMGT3 Test",
        car_file="test.veh",
        lap=1,
        lap_distance=1000.0,
        on_track=True,
        on_pit_road=False,
        in_garage=False,
        speed=50.0,
        throttle=0.8,
        brake=0.0,
        clutch=0.0,
        steering=-0.1,
        gear=4,
        rpm=7000.0,
        long_accel=1.2,
        lat_accel=-3.4,
        yaw_rate=0.2,
        yaw_north=1.0,
        position_x=100.0,
        position_y=200.0,
        altitude=5.0,
        velocity_x=1.0,
        velocity_y=50.0,
        lap_invalidated=False,
        track_limits=0,
        surface_type=0,
    )
    return replace(base, **overrides)


def create_duckdb(path: Path, laps: int = 5) -> None:
    frequency = 20
    lap_seconds = 10
    count = laps * lap_seconds * frequency
    start = 1000.0
    time_values = start + np.arange(count) / frequency
    phase = np.arange(count) % (lap_seconds * frequency)
    lap_distance = phase / (lap_seconds * frequency) * 5000
    throttle = np.where(phase < lap_seconds * frequency * 0.25, 0, 100)
    brake = np.where(phase < lap_seconds * frequency * 0.125, 80, 0)
    speed = 180 + 40 * np.sin(2 * np.pi * phase / (lap_seconds * frequency))
    steering = 25 * np.sin(4 * np.pi * phase / (lap_seconds * frequency))
    latitude = 50 + 0.002 * np.sin(2 * np.pi * phase / (lap_seconds * frequency))
    longitude = 5 + 0.003 * np.cos(2 * np.pi * phase / (lap_seconds * frequency))
    sampled = {
        "GPS Time": (frequency, time_values),
        "Lap Dist": (frequency, lap_distance),
        "Ground Speed": (frequency, speed),
        "Throttle Pos": (frequency, throttle),
        "Brake Pos": (frequency, brake),
        "Steering Pos": (frequency, steering),
        "Engine RPM": (frequency, np.full(count, 7000)),
        "GPS Latitude": (frequency, latitude),
        "GPS Longitude": (frequency, longitude),
        "Yaw Rate": (frequency, np.gradient(steering)),
        "G Force Long": (frequency, np.gradient(speed) / 9.80665),
        "G Force Lat": (frequency, steering / 100),
    }
    events = {
        "Lap": [
            (start + index * lap_seconds + (0.08 if index else 0), index)
            for index in range(laps)
        ],
        "Gear": [(start, 4)],
        "In Pits": [(start, 0)],
        "Lap Invalidated": [(start, 0)],
    }
    connection = duckdb.connect(str(path))
    connection.execute('CREATE TABLE metadata("key" VARCHAR, value VARCHAR)')
    connection.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [
            ("TrackName", "Circuit de Test"),
            ("TrackLayout", "Grand Prix"),
            ("CarName", "LMGT3 Test"),
            ("SessionType", "Practice"),
            ("Version", "1"),
        ],
    )
    connection.execute(
        "CREATE TABLE channelsList(channelName VARCHAR, frequency DOUBLE, unit VARCHAR)",
    )
    connection.execute("CREATE TABLE eventsList(eventName VARCHAR, unit VARCHAR)")
    for name, (channel_frequency, values) in sampled.items():
        connection.execute(f'CREATE TABLE "{name}"(value DOUBLE)')
        connection.executemany(
            f'INSERT INTO "{name}" VALUES (?)',
            [(float(value),) for value in values],
        )
        connection.execute(
            "INSERT INTO channelsList VALUES (?, ?, ?)",
            [name, channel_frequency, ""],
        )
    for name, values in events.items():
        connection.execute(f'CREATE TABLE "{name}"(ts DOUBLE, value DOUBLE)')
        connection.executemany(f'INSERT INTO "{name}" VALUES (?, ?)', values)
        connection.execute("INSERT INTO eventsList VALUES (?, ?)", [name, ""])
    connection.close()


def test_duckdb_reader_produces_lmu_report(tmp_path):
    path = tmp_path / "session.duckdb"
    create_duckdb(path)

    run = LmuDuckDbReader().read(path)
    report = analyze(run)

    assert run.metadata["simulator"] == "lmu"
    assert run.metadata["capture_source"] == "duckdb"
    assert np.isclose(np.max(run.samples["throttle"]), 1)
    assert np.isclose(np.max(run.samples["brake"]), 0.8)
    assert report.simulator == "lmu"
    assert report.capture_source == "duckdb"
    assert len(report.laps) == 5
    assert report.best_time == pytest.approx(9.95, abs=0.02)
    assert report.track_map.available
    assert report.track_map.source == "gps"


def test_duckdb_import_is_deduplicated_by_fingerprint(tmp_path):
    path = tmp_path / "session.duckdb"
    create_duckdb(path)
    run = LmuDuckDbReader().read(path)
    store = SessionStore(tmp_path / "data")

    first = store.add(run, "duckdb")
    second = store.add(run, "duckdb")

    assert first.session_id == second.session_id
    assert len(store.list()) == 1


def test_duckdb_reader_rejects_wrong_schema(tmp_path):
    path = tmp_path / "bad.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE TABLE metadata(key VARCHAR, value VARCHAR)")
    connection.close()

    with pytest.raises(ValueError, match="missing"):
        LmuDuckDbReader().read(path)


def test_run_builder_keeps_stints_and_flushes_on_session_change():
    builder = LmuRunBuilder()

    assert builder.ingest(snapshot()) == []
    assert builder.ingest(snapshot(session_time=10.02, lap_distance=1005)) == []
    assert builder.ingest(snapshot(session_time=11, on_track=False, in_garage=True)) == []
    assert builder.ingest(snapshot(session_time=12, lap_distance=1200)) == []
    completed = builder.ingest(snapshot(
        session_time=1, session_number=5, session_start=12500, lap=0, lap_distance=0,
    ))

    assert len(completed) == 1
    run = completed[0]
    assert run.metadata["session_type"] == "Practice 1"
    assert run.samples["capture_epoch"].tolist() == [0, 0, 1]
    assert run.samples["enter_exit_reset"].tolist() == [0, 0, 1]
    assert builder.metadata["session_type"] == "Qualifying 1"


def test_run_builder_flushes_only_once_at_session_over():
    builder = LmuRunBuilder()
    builder.ingest(snapshot())

    first = builder.ingest(snapshot(session_time=20, game_phase=8))
    second = builder.ingest(snapshot(session_time=21, game_phase=8))

    assert len(first) == 1
    assert second == []


def test_shared_memory_parser_selects_player_and_maps_channels():
    data = LMUObjectOut()
    data.generic.gameVersion = 120
    data.generic.events.SME_UPDATE_SCORING = 1
    data.generic.events.SME_UPDATE_TELEMETRY = 1
    data.scoring.scoringInfo.mNumVehicles = 2
    data.scoring.scoringInfo.mTrackName = b"Le Mans"
    data.scoring.scoringInfo.mSession = 10
    data.scoring.scoringInfo.mGamePhase = 5
    data.scoring.scoringInfo.mInRealtime = True
    data.scoring.scoringInfo.mLapDist = 13626
    data.scoring.scoringInfo.mStartET = 123
    data.telemetry.activeVehicles = 2
    data.telemetry.playerHasVehicle = True
    data.scoring.vehScoringInfo[1].mID = 42
    data.scoring.vehScoringInfo[1].mIsPlayer = True
    data.scoring.vehScoringInfo[1].mSteamID = 999
    data.scoring.vehScoringInfo[1].mLapDist = 6813
    data.telemetry.telemInfo[1].mID = 42
    data.telemetry.telemInfo[1].mElapsedTime = 12.5
    data.telemetry.telemInfo[1].mLapNumber = 3
    data.telemetry.telemInfo[1].mFilteredThrottle = 0.7
    data.telemetry.telemInfo[1].mFilteredBrake = 0.2
    data.telemetry.telemInfo[1].mFilteredSteering = -0.4
    data.telemetry.telemInfo[1].mLocalVel.z = 50
    data.telemetry.telemInfo[1].mPos.x = 100
    data.telemetry.telemInfo[1].mPos.z = 200

    parsed = LmuSharedMemorySource.parse(bytes(data))

    assert parsed is not None
    assert parsed.player_id == 42
    assert parsed.track == "Le Mans"
    assert parsed.lap == 3
    assert parsed.lap_distance == pytest.approx(6813)
    assert parsed.speed == pytest.approx(50)
    assert parsed.throttle == pytest.approx(0.7)
    assert parsed.position_x == pytest.approx(100)
    assert parsed.position_y == pytest.approx(200)


def test_world_coordinates_are_used_for_lmu_map():
    builder = LmuRunBuilder()
    samples = []
    for lap in range(1, 5):
        for index in range(240):
            angle = 2 * np.pi * index / 240
            samples.extend(builder.ingest(snapshot(
                session_time=(lap - 1) * 60 + index * 0.25,
                lap=lap,
                lap_distance=5000 * index / 240,
                position_x=500 * np.cos(angle),
                position_y=300 * np.sin(angle),
                speed=5000 / 60,
                steering=0.2 * np.sin(angle),
                yaw_rate=0.1 * np.sin(angle),
                lat_accel=2 * np.sin(angle),
            )))
    assert samples == []
    report = analyze(builder.finish())

    assert report.track_map.available
    assert report.track_map.source == "world_xy"
