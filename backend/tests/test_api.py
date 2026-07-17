import os
import tempfile

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
