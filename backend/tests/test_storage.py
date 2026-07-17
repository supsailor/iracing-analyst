from iracing_analyst.fixture import synthetic_run
from iracing_analyst.storage import SessionStore
from iracing_analyst.models import TelemetryRun
import numpy as np
import sqlite3
import json


def test_round_trip(tmp_path):
    store = SessionStore(tmp_path)
    report = store.add(synthetic_run(), "fixture")
    assert store.report(report.session_id) == report
    assert store.run(report.session_id) is not None
    assert store.list()[0].id == report.session_id


def test_live_fragments_with_same_identity_are_upserted(tmp_path):
    store = SessionStore(tmp_path)
    run = synthetic_run()
    split = 3 * 1200
    first = TelemetryRun({key: np.asarray(value)[:split] for key, value in run.samples.items()}, run.metadata)
    second = TelemetryRun({key: np.asarray(value)[split:] for key, value in run.samples.items()}, run.metadata)

    first_report = store.add(first, "live")
    second_report = store.add(second, "live")

    assert first_report.session_id == second_report.session_id
    assert len(store.list()) == 1
    assert len(second_report.laps) == 6


def test_delete_and_clear_are_explicit(tmp_path):
    store = SessionStore(tmp_path)
    first = store.add(synthetic_run(), "fixture")
    store.add(synthetic_run(), "fixture")
    assert store.delete(first.session_id)
    assert len(store.list()) == 1
    assert store.clear() == 1
    assert store.list() == []


def test_existing_database_is_migrated_without_deleting_rows(tmp_path):
    connection = sqlite3.connect(tmp_path / "sessions.sqlite3")
    connection.execute("""
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, track TEXT NOT NULL, car TEXT NOT NULL,
            source TEXT NOT NULL, status TEXT NOT NULL, telemetry_path TEXT NOT NULL,
            report_json TEXT, error TEXT
        )
    """)
    connection.commit()
    connection.close()

    store = SessionStore(tmp_path)

    columns = {row[1] for row in store.connection.execute("PRAGMA table_info(sessions)")}
    assert {"session_key", "session_type", "layout"} <= columns


def test_old_report_is_automatically_reanalyzed_without_rewriting_npz(tmp_path):
    initial = SessionStore(tmp_path)
    report = initial.add(synthetic_run(), "fixture")
    telemetry_path = initial.connection.execute(
        "SELECT telemetry_path FROM sessions WHERE id=?", (report.session_id,),
    ).fetchone()[0]
    before = open(telemetry_path, "rb").read()
    old_report = report.model_dump(mode="json")
    old_report.pop("analysis_version")
    initial.connection.execute(
        "UPDATE sessions SET report_json=? WHERE id=?",
        (json.dumps(old_report), report.session_id),
    )
    initial.connection.commit()
    initial.connection.close()

    migrated = SessionStore(tmp_path)

    assert migrated.report(report.session_id).analysis_version == 2
    assert open(telemetry_path, "rb").read() == before
