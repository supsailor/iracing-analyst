from __future__ import annotations

import sqlite3
import threading
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
        self._lock = threading.RLock()
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, track TEXT NOT NULL, car TEXT NOT NULL,
                source TEXT NOT NULL, status TEXT NOT NULL, telemetry_path TEXT NOT NULL,
                report_json TEXT, error TEXT
            )
        """)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(sessions)")}
        for name, declaration in (
            ("session_key", "TEXT"), ("session_type", "TEXT"), ("layout", "TEXT"),
        ):
            if name not in columns:
                self.connection.execute(f"ALTER TABLE sessions ADD COLUMN {name} {declaration}")
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_session_key ON sessions(session_key)",
        )
        self.connection.commit()

    def add(self, run: TelemetryRun, source: str | None = None) -> AnalysisReport:
        metadata = dict(run.metadata)
        metadata["source"] = source or str(metadata.get("source", "npz"))
        session_key = str(metadata.get("session_key", "")).strip()
        with self._lock:
            existing = None
            if metadata["source"] == "live" and session_key:
                existing = self.connection.execute(
                    "SELECT id FROM sessions WHERE session_key = ? ORDER BY created_at DESC LIMIT 1",
                    (session_key,),
                ).fetchone()
            if existing:
                session_id = existing["id"]
                previous = self.run(session_id)
                if previous:
                    run = self._merge(previous, TelemetryRun(run.samples, metadata))
                    metadata = dict(run.metadata)
            else:
                session_id = uuid.uuid4().hex
            path = self.telemetry_dir / f"{session_id}.npz"
            self._save_run(path, run, metadata)
            report = analyze(TelemetryRun(run.samples, metadata), session_id)
            values = (
                report.created_at.isoformat(), report.track, report.car, metadata["source"], "ready",
                str(path), report.model_dump_json(), None, session_key or None,
                report.session_type, report.layout, session_id,
            )
            if existing:
                self.connection.execute("""
                    UPDATE sessions SET created_at=?, track=?, car=?, source=?, status=?, telemetry_path=?,
                    report_json=?, error=?, session_key=?, session_type=?, layout=? WHERE id=?
                """, values)
            else:
                self.connection.execute("""
                    INSERT INTO sessions (
                        created_at, track, car, source, status, telemetry_path, report_json, error,
                        session_key, session_type, layout, id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, values)
            self.connection.commit()
            return report

    def _save_run(self, path: Path, run: TelemetryRun, metadata: dict[str, object]) -> None:
        arrays = {key: np.asarray(value) for key, value in run.samples.items()}
        arrays.update({f"meta_{key}": np.array(str(value)) for key, value in metadata.items()})
        np.savez_compressed(path, **arrays)

    def _merge(self, previous: TelemetryRun, fragment: TelemetryRun) -> TelemetryRun:
        keys = set(previous.samples) | set(fragment.samples)
        previous_len = len(np.asarray(previous.samples.get("session_time", [])))
        fragment_len = len(np.asarray(fragment.samples.get("session_time", [])))
        merged = {}
        for key in keys:
            left = np.asarray(previous.samples.get(key, np.zeros(previous_len)))
            right = np.asarray(fragment.samples.get(key, np.zeros(fragment_len)))
            merged[key] = np.concatenate((left, right))
        identity = np.asarray(merged.get("session_tick", []))
        if not identity.size or np.all(identity == 0):
            identity = np.round(np.asarray(merged["session_time"], dtype=float), 4)
        _, unique = np.unique(identity, return_index=True)
        order = unique[np.argsort(np.asarray(merged["session_time"])[unique])]
        merged = {key: values[order] for key, values in merged.items()}
        metadata = dict(previous.metadata)
        metadata.update(fragment.metadata)
        return TelemetryRun(merged, metadata)

    def list(self) -> list[SessionListItem]:
        rows = self.connection.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            report = AnalysisReport.model_validate_json(row["report_json"]) if row["report_json"] else None
            result.append(SessionListItem(
                id=row["id"], created_at=datetime.fromisoformat(row["created_at"]), track=row["track"],
                car=row["car"], source=row["source"], laps=len(report.laps) if report else 0,
                best_time=report.best_time if report else None, status=row["status"],
                session_type=report.session_type if report else (row["session_type"] or "Session"),
                layout=report.layout if report else (row["layout"] or ""),
                valid_laps=sum(lap.valid for lap in report.laps) if report else 0,
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

    def delete(self, session_id: str) -> bool:
        with self._lock:
            row = self.connection.execute(
                "SELECT telemetry_path FROM sessions WHERE id = ?", (session_id,),
            ).fetchone()
            if not row:
                return False
            self.connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            self.connection.commit()
            Path(row["telemetry_path"]).unlink(missing_ok=True)
            return True

    def clear(self) -> int:
        with self._lock:
            rows = self.connection.execute("SELECT telemetry_path FROM sessions").fetchall()
            self.connection.execute("DELETE FROM sessions")
            self.connection.commit()
            for row in rows:
                Path(row["telemetry_path"]).unlink(missing_ok=True)
            return len(rows)
