from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


CHANNELS = (
    "session_time", "lap", "lap_dist_pct", "speed", "throttle", "brake", "steering",
    "gear", "rpm", "long_accel", "lat_accel", "yaw", "yaw_rate", "on_pit_road",
    "track_surface", "incidents", "session_num", "session_state", "session_unique_id",
    "session_tick", "is_on_track_car", "enter_exit_reset", "latitude", "longitude",
    "altitude", "yaw_north", "velocity_x", "velocity_y",
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


class Insight(BaseModel):
    id: str
    kind: Literal["positive", "attention", "warning"]
    status: Literal["confirmed", "probable", "insufficient"]
    segment_id: str
    channel: Literal["speed", "throttle", "brake", "steering", "delta"]
    distance_pct: float = Field(ge=0, le=1)
    title_key: str
    message_key: str
    time_delta: float = 0
    evidence: list[Evidence] = Field(default_factory=list)


class MapPoint(BaseModel):
    distance_pct: float
    x: float
    y: float


class TrackMarker(BaseModel):
    label: str
    distance_pct: float
    x: float
    y: float
    insight_id: str | None = None


class TrackMap(BaseModel):
    available: bool = False
    source: Literal["gps", "integrated", "unavailable"] = "unavailable"
    centerline: list[MapPoint] = Field(default_factory=list)
    best: list[MapPoint] = Field(default_factory=list)
    median: list[MapPoint] = Field(default_factory=list)
    corners: list[TrackMarker] = Field(default_factory=list)
    insights: list[TrackMarker] = Field(default_factory=list)


class StintSummary(BaseModel):
    index: int
    start_time: float
    end_time: float
    first_lap: int
    last_lap: int


class DataSufficiency(BaseModel):
    status: Literal["ready", "limited", "insufficient"]
    valid_laps: int
    required_laps: int = 3
    message_key: str


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
    confidence: float = 0
    session_type: str = "Practice"
    layout: str = ""
    track_id: int | None = None
    official_turns: int | None = None
    stints: list[StintSummary] = Field(default_factory=list)
    track_map: TrackMap = Field(default_factory=TrackMap)
    insights: list[Insight] = Field(default_factory=list)
    strengths: list[Insight] = Field(default_factory=list)
    improvement_actions: list[Recommendation] = Field(default_factory=list)
    data_sufficiency: DataSufficiency = Field(default_factory=lambda: DataSufficiency(
        status="insufficient", valid_laps=0, message_key="data.insufficient",
    ))


class SessionListItem(BaseModel):
    id: str
    created_at: datetime
    track: str
    car: str
    source: Literal["live", "ibt", "fixture", "npz"]
    laps: int
    best_time: float | None
    status: Literal["recording", "ready", "failed"]
    session_type: str = "Practice"
    layout: str = ""
    valid_laps: int = 0


class HealthResponse(BaseModel):
    status: str = "ok"
    simulator_connected: bool
    recording: bool
    version: str


class TelemetrySeries(BaseModel):
    distance_pct: list[float]
    selected: dict[str, list[float]]
    reference: dict[str, list[float]]
