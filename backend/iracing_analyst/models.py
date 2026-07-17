from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CHANNELS = (
    "session_time", "lap", "lap_dist_pct", "speed", "throttle", "brake", "steering",
    "gear", "rpm", "long_accel", "lat_accel", "yaw", "yaw_rate", "on_pit_road",
    "track_surface", "incidents",
)


@dataclass(slots=True)
class TelemetryRun:
    samples: dict[str, object]
    metadata: dict[str, object]


class Evidence(BaseModel):
    metric: str
    value: float
    unit: str
    comparison: float | None = None


class Recommendation(BaseModel):
    rule: str
    segment_id: str
    title_key: str
    message_key: str
    confidence: float = Field(ge=0, le=1)
    expected_gain: float = Field(ge=0)
    evidence: list[Evidence]


class SegmentMetrics(BaseModel):
    id: str
    name: str
    start_pct: float
    end_pct: float
    confidence: float
    best_time: float
    median_time: float
    selected_time: float
    delta_to_best: float
    stability: float
    source_lap: int
    entry_speed_kph: float
    minimum_speed_kph: float
    exit_speed_kph: float
    brake_start_pct: float | None = None
    brake_release_pct: float | None = None
    throttle_start_pct: float | None = None
    full_throttle_pct: float | None = None
    steering_corrections: int = 0


class LapSummary(BaseModel):
    number: int
    time: float
    valid: bool
    representative: bool
    reason: str | None = None


class AnalysisReport(BaseModel):
    session_id: str
    track: str
    car: str
    created_at: datetime
    sample_count: int
    laps: list[LapSummary]
    best_lap: int | None
    best_time: float | None
    median_lap: int | None
    median_time: float | None
    sector_optimal: float | None
    potential_gap: float | None
    segments: list[SegmentMetrics]
    recommendations: list[Recommendation]
    confidence: float


class SessionListItem(BaseModel):
    id: str
    created_at: datetime
    track: str
    car: str
    source: Literal["live", "ibt", "fixture", "npz"]
    laps: int
    best_time: float | None
    status: Literal["recording", "ready", "failed"]


class HealthResponse(BaseModel):
    status: str = "ok"
    simulator_connected: bool
    recording: bool
    version: str


class TelemetrySeries(BaseModel):
    distance_pct: list[float]
    selected: dict[str, list[float]]
    reference: dict[str, list[float]]

