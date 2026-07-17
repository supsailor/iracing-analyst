from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np

from .models import (
    AnalysisReport, DataSufficiency, Evidence, Insight, LapSummary, MapPoint, Recommendation,
    SegmentMetrics, StintSummary, TelemetryRun, TrackMap, TrackMarker,
)
from .track_catalog import catalog_for


GRID_SIZE = 1200


@dataclass(slots=True)
class NormalizedLap:
    number: int
    time: float
    grid: np.ndarray
    values: dict[str, np.ndarray]
    valid: bool = True
    representative: bool = True
    reason: str | None = None


def _as_float(run: TelemetryRun, key: str, default: float = 0.0) -> np.ndarray:
    reference = np.asarray(run.samples["session_time"])
    value = run.samples.get(key)
    if value is None:
        return np.full(reference.shape, default, dtype=float)
    return np.asarray(value, dtype=float)


def normalize_laps(run: TelemetryRun) -> list[NormalizedLap]:
    time = _as_float(run, "session_time")
    lap_no = _as_float(run, "lap").astype(int)
    dist = _as_float(run, "lap_dist_pct")
    pit = _as_float(run, "on_pit_road").astype(bool)
    surface = _as_float(run, "track_surface", 3)
    channels = [
        "speed", "throttle", "brake", "steering", "gear", "rpm", "long_accel",
        "lat_accel", "yaw", "yaw_rate", "incidents", "latitude", "longitude", "altitude",
        "yaw_north", "velocity_x", "velocity_y", "enter_exit_reset",
    ]
    grid = np.linspace(0.0, 1.0, GRID_SIZE, endpoint=False)
    result: list[NormalizedLap] = []
    for number in sorted(set(lap_no.tolist())):
        mask = lap_no == number
        if number <= 0 or mask.sum() < 120:
            continue
        indices = np.flatnonzero(mask)
        lap_dist = dist[indices]
        order = np.argsort(lap_dist)
        indices, lap_dist = indices[order], lap_dist[order]
        unique_dist, unique_index = np.unique(lap_dist, return_index=True)
        indices = indices[unique_index]
        coverage = float(unique_dist[-1] - unique_dist[0]) if unique_dist.size else 0
        duration = float(time[indices[-1]] - time[indices[0]])
        has_pit = bool(pit[indices].any())
        missing = coverage < 0.94 or unique_dist.size < 120
        stopped = duration <= 0 or bool(np.mean(_as_float(run, "speed")[indices] < 1.0) > 0.08)
        offtrack_share = float(np.mean(surface[indices] == 0))
        valid = not (has_pit or missing or stopped or offtrack_share > 0.08)
        reason = "pit" if has_pit else "missing_data" if missing else "stopped" if stopped else (
            "off_track" if offtrack_share > 0.08 else None
        )
        values = {}
        for channel in channels:
            raw = _as_float(run, channel)[indices]
            values[channel] = np.interp(grid, unique_dist, raw)
        values["elapsed"] = np.interp(grid, unique_dist, time[indices] - time[indices[0]])
        result.append(NormalizedLap(number, duration, grid, values, valid, valid, reason))

    valid_times = np.array([lap.time for lap in result if lap.valid])
    if valid_times.size >= 3:
        median = float(np.median(valid_times))
        mad = float(np.median(np.abs(valid_times - median)))
        tolerance = max(0.02 * median, 3.5 * mad)
        for lap in result:
            lap.representative = lap.valid and abs(lap.time - median) <= tolerance
    return result


def _smooth(values: np.ndarray, width: int = 17) -> np.ndarray:
    if width <= 1:
        return values
    kernel = np.ones(width) / width
    return np.convolve(values, kernel, mode="same")


def detect_segments(laps: list[NormalizedLap]) -> list[tuple[int, int, float]]:
    representative = [lap for lap in laps if lap.representative]
    if not representative:
        return [(i, min(i + GRID_SIZE // 6, GRID_SIZE), 0.25) for i in range(0, GRID_SIZE, GRID_SIZE // 6)]
    median = min(representative, key=lambda lap: abs(lap.time - np.median([x.time for x in representative])))
    steering = np.abs(_smooth(median.values["steering"]))
    yaw_rate = np.abs(_smooth(median.values["yaw_rate"]))
    lat = np.abs(_smooth(median.values["lat_accel"]))
    speed = _smooth(median.values["speed"])
    def robust_scale(v: np.ndarray) -> np.ndarray:
        q50, q90 = np.quantile(v, [0.5, 0.9])
        return np.clip((v - q50) / max(q90 - q50, 1e-6), 0, 2)
    score = 0.45 * robust_scale(steering) + 0.35 * robust_scale(yaw_rate) + 0.2 * robust_scale(lat)
    score += 0.15 * robust_scale(np.maximum(np.max(speed) - speed, 0))
    active = score > 0.48
    runs: list[list[int]] = []
    start = None
    for i, enabled in enumerate(active):
        if enabled and start is None:
            start = i
        if start is not None and (not enabled or i == GRID_SIZE - 1):
            end = i if not enabled else i + 1
            if end - start >= 12:
                runs.append([max(0, start - 14), min(GRID_SIZE, end + 18)])
            start = None
    merged: list[list[int]] = []
    for run in runs:
        if merged and run[0] - merged[-1][1] < 20:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    if len(merged) < 2:
        step = GRID_SIZE // 6
        return [(i, min(i + step, GRID_SIZE), 0.25) for i in range(0, GRID_SIZE, step)]
    boundaries = [0]
    for left, right in zip(merged, merged[1:]):
        boundaries.append((left[1] + right[0]) // 2)
    boundaries.append(GRID_SIZE)
    return [(boundaries[i], boundaries[i + 1], min(0.95, 0.55 + float(np.max(score[a:b])) * 0.2))
            for i, (a, b) in enumerate(zip(boundaries, boundaries[1:]))]


def report_segments(run: TelemetryRun, laps: list[NormalizedLap]) -> list[tuple[int, int, float, str]]:
    catalog = catalog_for(run.metadata)
    if catalog:
        return [
            (round(item.start_pct * GRID_SIZE), round(item.end_pct * GRID_SIZE), 1.0, item.name)
            for item in catalog
        ]
    return [(start, end, confidence, f"Zone {index}") for index, (start, end, confidence) in enumerate(detect_segments(laps), 1)]


def _crossing(values: np.ndarray, threshold: float, start: int, end: int, rising: bool) -> int | None:
    view = values[start:end]
    mask = view >= threshold if rising else view <= threshold
    found = np.flatnonzero(mask)
    return int(start + found[0]) if found.size else None


def _segment_time(lap: NormalizedLap, a: int, b: int) -> float:
    elapsed = lap.values["elapsed"]
    if b >= len(elapsed):
        tail = lap.time - float(elapsed[a])
        return max(tail, 0.0)
    return max(float(elapsed[b] - elapsed[a]), 0.0)


def _metrics(lap: NormalizedLap, a: int, b: int) -> dict[str, float | int | None]:
    speed = lap.values["speed"][a:b] * 3.6
    brake, throttle, steering = (lap.values[key][a:b] for key in ("brake", "throttle", "steering"))
    apex = int(np.argmin(speed)) if speed.size else 0
    brake_on = _crossing(brake, 0.08, 0, len(brake), True)
    brake_release = None
    if brake_on is not None:
        brake_release = _crossing(brake, 0.05, brake_on, len(brake), False)
    throttle_on = _crossing(throttle, 0.2, apex, len(throttle), True)
    full = _crossing(throttle, 0.95, apex, len(throttle), True)
    corrections = int(np.sum(np.diff(np.sign(np.diff(_smooth(steering, 5)))) != 0))
    def pct(value: int | None) -> float | None:
        return None if value is None else (a + value) / GRID_SIZE
    return {
        "entry": float(speed[0]), "minimum": float(np.min(speed)), "exit": float(speed[-1]),
        "brake_start": pct(brake_on), "brake_release": pct(brake_release),
        "throttle_start": pct(throttle_on), "full_throttle": pct(full), "corrections": corrections,
    }


def build_recommendations(segments: list[SegmentMetrics]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for segment in sorted(segments, key=lambda s: s.delta_to_best, reverse=True):
        if segment.delta_to_best < 0.035 or segment.confidence < 0.5:
            continue
        evidence = [Evidence(metric="time_loss", value=segment.delta_to_best, unit="s")]
        if segment.stability > 0.12:
            rule, title, message = "inconsistent", "rec.inconsistent.title", "rec.inconsistent.message"
            evidence.append(Evidence(metric="time_spread", value=segment.stability, unit="s"))
        elif segment.full_throttle_pct is not None and segment.throttle_start_pct is not None and segment.full_throttle_pct - segment.throttle_start_pct > 0.018:
            rule, title, message = "late_throttle", "rec.lateThrottle.title", "rec.lateThrottle.message"
            evidence.append(Evidence(metric="throttle_ramp", value=(segment.full_throttle_pct - segment.throttle_start_pct) * 100, unit="% lap"))
        elif segment.minimum_speed_kph + 4 < min(segment.entry_speed_kph, segment.exit_speed_kph):
            rule, title, message = "low_min_speed", "rec.lowSpeed.title", "rec.lowSpeed.message"
            evidence.append(Evidence(metric="minimum_speed", value=segment.minimum_speed_kph, unit="km/h"))
        elif segment.steering_corrections >= 5:
            rule, title, message = "steering_corrections", "rec.corrections.title", "rec.corrections.message"
            evidence.append(Evidence(metric="corrections", value=segment.steering_corrections, unit="count"))
        else:
            rule, title, message = "segment_loss", "rec.segment.title", "rec.segment.message"
        recommendations.append(Recommendation(
            rule=rule, segment_id=segment.id, title_key=title, message_key=message,
            confidence=min(segment.confidence, 0.55 + segment.delta_to_best * 2),
            expected_gain=segment.delta_to_best, evidence=evidence,
        ))
        if len(recommendations) == 3:
            break
    return recommendations


def build_insights(
    segments: list[SegmentMetrics], median_lap: NormalizedLap, valid_count: int,
) -> list[Insight]:
    if valid_count < 3:
        return []
    status = "confirmed" if valid_count >= 5 else "probable"
    insights = []
    for segment in segments:
        median_segment_time = _segment_time(
            median_lap, round(segment.start_pct * GRID_SIZE), round(segment.end_pct * GRID_SIZE),
        )
        gain = median_segment_time - segment.selected_time
        if gain < 0.025:
            continue
        channel = "delta"
        if segment.full_throttle_pct is not None:
            channel = "throttle"
        elif segment.brake_release_pct is not None:
            channel = "brake"
        insights.append(Insight(
            id=f"insight-{segment.id}", kind="positive", status=status,
            segment_id=segment.id, channel=channel,
            distance_pct=(segment.start_pct + segment.end_pct) / 2,
            title_key="insight.faster.title", message_key="insight.faster.message",
            time_delta=-gain,
            evidence=[Evidence(metric="time_gain", value=gain, unit="s")],
        ))
    return sorted(insights, key=lambda item: item.time_delta)[:3]


def detect_stints(run: TelemetryRun) -> list[StintSummary]:
    time_values = _as_float(run, "session_time")
    laps = _as_float(run, "lap").astype(int)
    if not time_values.size:
        return []
    breaks = np.flatnonzero(np.diff(time_values) > 2.0) + 1
    ranges = np.split(np.arange(len(time_values)), breaks)
    result = []
    for index, indices in enumerate(ranges, 1):
        if indices.size < 2:
            continue
        positive_laps = laps[indices][laps[indices] > 0]
        result.append(StintSummary(
            index=index, start_time=float(time_values[indices[0]]), end_time=float(time_values[indices[-1]]),
            first_lap=int(positive_laps.min()) if positive_laps.size else 0,
            last_lap=int(positive_laps.max()) if positive_laps.size else 0,
        ))
    return result


def _trajectory(lap: NormalizedLap) -> tuple[list[MapPoint], str]:
    lat = lap.values["latitude"]
    lon = lap.values["longitude"]
    valid_gps = np.ptp(lat) > 1e-7 and np.ptp(lon) > 1e-7
    if valid_gps:
        lat0, lon0 = float(lat[0]), float(lon[0])
        x = (lon - lon0) * 111_320 * np.cos(np.radians(lat0))
        y = (lat - lat0) * 110_540
        source = "gps"
    else:
        elapsed = lap.values["elapsed"]
        dt = np.maximum(np.diff(elapsed, prepend=elapsed[0]), 0)
        heading = lap.values["yaw_north"]
        vx, vy = lap.values["velocity_x"], lap.values["velocity_y"]
        world_x = vx * np.cos(heading) - vy * np.sin(heading)
        world_y = vx * np.sin(heading) + vy * np.cos(heading)
        x, y = np.cumsum(world_x * dt), np.cumsum(world_y * dt)
        if np.ptp(x) < 10 or np.ptp(y) < 10:
            return [], "unavailable"
        correction = np.linspace(0, 1, GRID_SIZE)
        x -= correction * (x[-1] - x[0])
        y -= correction * (y[-1] - y[0])
        source = "integrated"
    return [
        MapPoint(distance_pct=float(lap.grid[index]), x=float(x[index]), y=float(y[index]))
        for index in range(0, GRID_SIZE, 6)
    ], source


def _point_at(points: list[MapPoint], distance_pct: float) -> MapPoint | None:
    return min(points, key=lambda point: abs(point.distance_pct - distance_pct)) if points else None


def build_track_map(
    best: NormalizedLap, median: NormalizedLap, segments: list[SegmentMetrics], insights: list[Insight],
) -> TrackMap:
    median_points, source = _trajectory(median)
    best_points, best_source = _trajectory(best)
    if not median_points:
        return TrackMap()
    corners = []
    for segment in segments:
        point = _point_at(median_points, segment.start_pct)
        if point:
            corners.append(TrackMarker(label=segment.name, distance_pct=segment.start_pct, x=point.x, y=point.y))
    markers = []
    for insight in insights:
        point = _point_at(median_points, insight.distance_pct)
        if point:
            markers.append(TrackMarker(
                label="✓" if insight.kind == "positive" else "!", distance_pct=insight.distance_pct,
                x=point.x, y=point.y, insight_id=insight.id,
            ))
    return TrackMap(
        available=True, source=source if source == best_source else source,
        centerline=median_points, best=best_points, median=median_points, corners=corners, insights=markers,
    )


def analyze(run: TelemetryRun, session_id: str | None = None) -> AnalysisReport:
    laps = normalize_laps(run)
    representative = [lap for lap in laps if lap.representative]
    valid = [lap for lap in laps if lap.valid]
    session_id = session_id or uuid.uuid4().hex
    session_type = str(run.metadata.get("session_type", "Practice"))
    layout = str(run.metadata.get("layout", ""))
    def optional_int(key: str) -> int | None:
        try:
            return int(str(run.metadata.get(key, "")))
        except ValueError:
            return None
    if not valid:
        return AnalysisReport(
            session_id=session_id, track=str(run.metadata.get("track", "Unknown track")),
            car=str(run.metadata.get("car", "Unknown car")), created_at=datetime.now(timezone.utc),
            sample_count=len(_as_float(run, "session_time")),
            laps=[LapSummary(number=x.number, time=x.time, valid=x.valid, representative=x.representative, reason=x.reason) for x in laps],
            best_lap=None, best_time=None, median_lap=None, median_time=None, sector_optimal=None,
            potential_gap=None, segments=[], recommendations=[], confidence=0.0,
            session_type=session_type, layout=layout, track_id=optional_int("track_id"),
            official_turns=optional_int("official_turns"), stints=detect_stints(run),
            data_sufficiency=DataSufficiency(status="insufficient", valid_laps=0, message_key="data.noValidLaps"),
        )
    best = min(valid, key=lambda x: x.time)
    pool = representative or valid
    median_value = float(np.median([lap.time for lap in pool]))
    median = min(pool, key=lambda x: abs(x.time - median_value))
    detected = report_segments(run, laps)
    segments: list[SegmentMetrics] = []
    sector_optimal = 0.0
    for index, (a, b, confidence, segment_name) in enumerate(detected, 1):
        times = [(lap, _segment_time(lap, a, b)) for lap in pool]
        source, best_segment_time = min(times, key=lambda item: item[1])
        selected_time = _segment_time(best, a, b)
        source_metrics = _metrics(source, a, b)
        time_values = np.array([value for _, value in times])
        sector_optimal += best_segment_time
        segments.append(SegmentMetrics(
            id=f"segment-{index}", name=segment_name, start_pct=a / GRID_SIZE, end_pct=b / GRID_SIZE,
            confidence=confidence, best_time=best_segment_time, median_time=float(np.median(time_values)),
            selected_time=selected_time, delta_to_best=max(0, selected_time - best_segment_time),
            stability=float(np.median(np.abs(time_values - np.median(time_values)))), source_lap=source.number,
            entry_speed_kph=source_metrics["entry"], minimum_speed_kph=source_metrics["minimum"],
            exit_speed_kph=source_metrics["exit"], brake_start_pct=source_metrics["brake_start"],
            brake_release_pct=source_metrics["brake_release"], throttle_start_pct=source_metrics["throttle_start"],
            full_throttle_pct=source_metrics["full_throttle"], steering_corrections=source_metrics["corrections"],
        ))
    confidence = min(1.0, len(representative) / 5) * float(np.mean([s.confidence for s in segments]))
    enough_data = len(valid) >= 3
    recommendations = build_recommendations(segments) if enough_data else []
    insights = build_insights(segments, median, len(valid))
    sufficiency = DataSufficiency(
        status="ready" if len(valid) >= 5 else "limited" if enough_data else "insufficient",
        valid_laps=len(valid), message_key=(
            "data.ready" if len(valid) >= 5 else "data.limited" if enough_data else "data.needMoreLaps"
        ),
    )
    return AnalysisReport(
        session_id=session_id, track=str(run.metadata.get("track", "Unknown track")),
        car=str(run.metadata.get("car", "Unknown car")), created_at=datetime.now(timezone.utc),
        sample_count=len(_as_float(run, "session_time")),
        laps=[LapSummary(number=x.number, time=x.time, valid=x.valid, representative=x.representative, reason=x.reason) for x in laps],
        best_lap=best.number, best_time=best.time,
        median_lap=median.number if enough_data else None, median_time=median.time if enough_data else None,
        sector_optimal=sector_optimal if enough_data else None,
        potential_gap=max(0, best.time - sector_optimal) if enough_data else None,
        segments=segments, recommendations=recommendations, confidence=confidence,
        session_type=session_type, layout=layout, track_id=optional_int("track_id"),
        official_turns=optional_int("official_turns"), stints=detect_stints(run),
        insights=insights, strengths=insights, improvement_actions=recommendations,
        data_sufficiency=sufficiency,
        track_map=build_track_map(best, median, segments, insights),
    )


def telemetry_for_laps(run: TelemetryRun, selected_number: int, reference_number: int) -> dict:
    laps = {lap.number: lap for lap in normalize_laps(run)}
    selected, reference = laps[selected_number], laps[reference_number]
    channels = ("speed", "throttle", "brake", "steering")
    selected_data = {key: selected.values[key].tolist() for key in channels}
    reference_data = {key: reference.values[key].tolist() for key in channels}
    selected_data["delta"] = (selected.values["elapsed"] - reference.values["elapsed"]).tolist()
    reference_data["delta"] = np.zeros(GRID_SIZE).tolist()
    return {"distance_pct": selected.grid.tolist(), "selected": selected_data, "reference": reference_data}
