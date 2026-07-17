from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

import numpy as np

from .analysis import analyze
from .models import AnalysisReport, SessionListItem, TelemetryRun


class SessionStore:
    def __init__(self, root: Path):
        self.root = root
        self.telemetry_dir = root / "telemetry"
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(root / "sessions.sqlite3", check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, track TEXT NOT NULL, car TEXT NOT NULL,
                source TEXT NOT NULL, status TEXT NOT NULL, telemetry_path TEXT NOT NULL,
                report_json TEXT, error TEXT
            )
        """)
        self.connection.commit()

    def add(self, run: TelemetryRun, source: str | None = None) -> AnalysisReport:
        session_id = uuid.uuid4().hex
        path = self.telemetry_dir / f"{session_id}.npz"
        metadata = dict(run.metadata)
        metadata["source"] = source or str(metadata.get("source", "npz"))
        arrays = {key: np.asarray(value) for key, value in run.samples.items()}
        arrays.update({f"meta_{key}": np.array(str(value)) for key, value in metadata.items()})
        np.savez_compressed(path, **arrays)
        report = analyze(TelemetryRun(run.samples, metadata), session_id)
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, report.created_at.isoformat(), report.track, report.car, metadata["source"],
             "ready", str(path), report.model_dump_json(), None),
        )
        self.connection.commit()
        return report

    def list(self) -> list[SessionListItem]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            report = AnalysisReport.model_validate_json(row["report_json"]) if row["report_json"] else None
            result.append(SessionListItem(
                id=row["id"], created_at=datetime.fromisoformat(row["created_at"]), track=row["track"],
                car=row["car"], source=row["source"], laps=len(report.laps) if report else 0,
                best_time=report.best_time if report else None, status=row["status"],
            ))
        return result

    def report(self, session_id: str) -> AnalysisReport | None:
        row = self.connection.execute("SELECT report_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return AnalysisReport.model_validate_json(row[0]) if row and row[0] else None

    def run(self, session_id: str) -> TelemetryRun | None:
        row = self.connection.execute("SELECT telemetry_path FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if not row:
            return None
        with np.load(row[0], allow_pickle=False) as data:
            samples = {key: data[key] for key in data.files if not key.startswith("meta_")}
            metadata = {key[5:]: str(data[key].item()) for key in data.files if key.startswith("meta_")}
        return TelemetryRun(samples, metadata)
