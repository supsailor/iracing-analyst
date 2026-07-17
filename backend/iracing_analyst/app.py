from __future__ import annotations

import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .analysis import compare_laps, telemetry_for_laps
from .config import data_dir
from .ingest import IbtReader, LiveCollector, read_npz
from .models import AnalysisReport, HealthResponse, LapComparison, SessionListItem, TelemetrySeries
from .storage import SessionStore


store = SessionStore(data_dir())
collector = LiveCollector(lambda run: store.add(run, "live"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    collector.start()
    yield
    collector.stop()


app = FastAPI(title="iRacing Analyst", version=__version__, lifespan=lifespan)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(simulator_connected=collector.connected, recording=collector.recording, version=__version__)


@app.get("/api/sessions", response_model=list[SessionListItem])
def sessions() -> list[SessionListItem]:
    return store.list()


@app.get("/api/sessions/{session_id}", response_model=AnalysisReport)
def report(session_id: str) -> AnalysisReport:
    result = store.report(session_id)
    if not result:
        raise HTTPException(404, "Session not found")
    return result


@app.delete("/api/sessions/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    if not store.delete(session_id):
        raise HTTPException(404, "Session not found")


@app.delete("/api/sessions", status_code=200)
def clear_sessions(confirm: bool = False) -> dict[str, int]:
    if not confirm:
        raise HTTPException(400, "Explicit confirmation is required")
    return {"deleted": store.clear()}


@app.get("/api/sessions/{session_id}/telemetry", response_model=TelemetrySeries)
def telemetry(session_id: str, selected_lap: int, reference_lap: int) -> dict:
    run = store.run(session_id)
    if not run:
        raise HTTPException(404, "Session not found")
    try:
        return telemetry_for_laps(run, selected_lap, reference_lap)
    except KeyError as exc:
        raise HTTPException(400, "Lap is unavailable") from exc


@app.get("/api/sessions/{session_id}/comparison", response_model=LapComparison)
def comparison(session_id: str, selected_lap: int, reference_lap: int) -> LapComparison:
    run = store.run(session_id)
    if not run:
        raise HTTPException(404, "Session not found")
    try:
        return compare_laps(run, selected_lap, reference_lap)
    except KeyError as exc:
        raise HTTPException(400, "Lap is unavailable") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/import", response_model=AnalysisReport, status_code=201)
async def import_telemetry(file: UploadFile = File(...)) -> AnalysisReport:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".ibt", ".npz"}:
        raise HTTPException(415, "Only .ibt and .npz telemetry files are supported")
    with tempfile.TemporaryDirectory() as temporary:
        target = Path(temporary) / f"import{suffix}"
        with target.open("wb") as output:
            shutil.copyfileobj(file.file, output)
        try:
            run = IbtReader().read(target) if suffix == ".ibt" else read_npz(target)
            if suffix == ".ibt":
                run.metadata["original_name"] = file.filename or "telemetry.ibt"
            source = "ibt" if suffix == ".ibt" else str(run.metadata.get("source", "npz"))
            if source not in {"live", "ibt", "fixture", "npz"}:
                source = "npz"
            return store.add(run, source)
        except (ValueError, OSError) as exc:
            raise HTTPException(422, str(exc)) from exc


static = Path(__file__).with_name("static")
if static.exists():
    app.mount("/assets", StaticFiles(directory=static / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        candidate = static / path
        return FileResponse(candidate if path and candidate.is_file() else static / "index.html")
