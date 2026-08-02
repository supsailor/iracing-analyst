import os
import tempfile

import duckdb

os.environ["IRACING_ANALYST_DATA_DIR"] = tempfile.mkdtemp(prefix="iracing-analyst-test-")

from fastapi.testclient import TestClient

from iracing_analyst import app as app_module
from iracing_analyst.app import app
from iracing_analyst.fixture import write_fixture
from iracing_analyst.storage import SessionStore


def test_import_and_query(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", SessionStore(tmp_path / "store"))
    fixture = tmp_path / "demo.npz"
    write_fixture(fixture)
    with TestClient(app) as client, fixture.open("rb") as source:
        response = client.post("/api/import", files={"file": ("demo.npz", source, "application/octet-stream")})
        assert response.status_code == 201, response.text
        report = response.json()
        assert client.get("/api/sessions").json()[0]["id"] == report["session_id"]
        telemetry = client.get(
            f"/api/sessions/{report['session_id']}/telemetry",
            params={"selected_lap": report["best_lap"], "reference_lap": report["median_lap"]},
        )
        assert telemetry.status_code == 200
        assert len(telemetry.json()["distance_pct"]) == 1200
        comparison = client.get(
            f"/api/sessions/{report['session_id']}/comparison",
            params={"selected_lap": report["best_lap"], "reference_lap": report["median_lap"]},
        )
        assert comparison.status_code == 200
        assert comparison.json()["segments"]
        assert client.delete(f"/api/sessions/{report['session_id']}").status_code == 204


def test_clear_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", SessionStore(tmp_path / "clear-store"))
    with TestClient(app) as client:
        assert client.delete("/api/sessions").status_code == 400
        assert client.delete("/api/sessions?confirm=true").json() == {"deleted": 0}


def test_import_lmu_duckdb(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "store", SessionStore(tmp_path / "lmu-store"))
    telemetry = tmp_path / "lmu.duckdb"
    connection = duckdb.connect(str(telemetry))
    connection.execute('CREATE TABLE metadata("key" VARCHAR, value VARCHAR)')
    connection.executemany(
        "INSERT INTO metadata VALUES (?, ?)",
        [("TrackName", "LMU Test"), ("CarName", "LMGT3"), ("SessionType", "Practice")],
    )
    connection.execute(
        "CREATE TABLE channelsList(channelName VARCHAR, frequency DOUBLE, unit VARCHAR)",
    )
    connection.executemany(
        "INSERT INTO channelsList VALUES (?, ?, ?)",
        [("GPS Time", 1, "s"), ("Lap Dist", 1, "m")],
    )
    connection.execute("CREATE TABLE eventsList(eventName VARCHAR, unit VARCHAR)")
    connection.execute("INSERT INTO eventsList VALUES ('Lap', '')")
    connection.execute('CREATE TABLE "GPS Time"(value DOUBLE)')
    connection.execute('INSERT INTO "GPS Time" VALUES (0), (1), (2)')
    connection.execute('CREATE TABLE "Lap Dist"(value DOUBLE)')
    connection.execute('INSERT INTO "Lap Dist" VALUES (0), (500), (1000)')
    connection.execute('CREATE TABLE "Lap"(ts DOUBLE, value DOUBLE)')
    connection.execute('INSERT INTO "Lap" VALUES (0, 0)')
    connection.close()

    with TestClient(app) as client, telemetry.open("rb") as source:
        response = client.post(
            "/api/import",
            files={"file": ("lmu.duckdb", source, "application/octet-stream")},
        )

    assert response.status_code == 201, response.text
    assert response.json()["simulator"] == "lmu"
    assert response.json()["capture_source"] == "duckdb"
