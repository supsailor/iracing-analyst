import numpy as np

from iracing_analyst.analysis import analyze, compare_laps, normalize_laps, telemetry_for_laps
from iracing_analyst.fixture import synthetic_run


def test_finds_complete_laps_and_summary():
    run = synthetic_run()
    report = analyze(run, "test")
    assert len(report.laps) == 6
    assert report.best_lap is not None
    assert report.median_lap is not None
    assert report.best_time <= report.median_time
    assert report.sector_optimal <= report.best_time + 0.01
    assert report.potential_gap >= 0
    assert len(report.segments) >= 2


def test_pit_lap_is_excluded_but_other_laps_remain():
    run = synthetic_run(4)
    run.samples["on_pit_road"][1200:1250] = 1
    laps = normalize_laps(run)
    assert not laps[1].valid
    assert laps[1].reason == "pit"
    assert sum(lap.valid for lap in laps) == 3


def test_in_lap_transition_is_classified():
    run = synthetic_run(3)
    lap_mask = run.samples["lap"] == 2
    run.samples["on_pit_road"][lap_mask & (run.samples["lap_dist_pct"] > 0.85)] = 1
    report = analyze(run)
    lap = next(item for item in report.laps if item.number == 2)
    assert lap.display_type == "in_lap"
    assert "in_lap" in lap.badges
    assert not lap.valid


def test_missing_data_lap_is_excluded():
    run = synthetic_run(3)
    mask = ~((run.samples["lap"] == 2) & (run.samples["lap_dist_pct"] > 0.7))
    run.samples = {key: np.asarray(value)[mask] for key, value in run.samples.items()}
    laps = normalize_laps(run)
    assert next(lap for lap in laps if lap.number == 2).reason == "missing_data"


def test_telemetry_series_are_aligned():
    run = synthetic_run()
    data = telemetry_for_laps(run, 1, 2)
    assert len(data["distance_pct"]) == 1200
    assert len(data["selected"]["delta"]) == 1200


def test_recommendations_are_bounded():
    report = analyze(synthetic_run())
    assert len(report.recommendations) <= 3
    assert all(0 <= item.confidence <= 1 for item in report.recommendations)


def test_two_laps_are_reported_as_insufficient():
    report = analyze(synthetic_run(2))
    assert report.data_sufficiency.status == "insufficient"
    assert report.median_time is None
    assert report.sector_optimal is None
    assert report.improvement_actions == []


def test_track_map_and_insights_are_structured():
    report = analyze(synthetic_run())
    assert report.track_map.available
    assert report.track_map.source == "gps"
    assert report.track_map.centerline
    assert report.data_sufficiency.status == "ready"


def test_spa_uses_official_corner_catalog():
    run = synthetic_run()
    run.metadata.update({"track": "Circuit de Spa-Francorchamps", "track_name": "spa", "official_turns": 19})
    report = analyze(run)
    assert report.official_turns == 19
    assert len(report.segments) == 19
    assert report.segments[0].name == "La Source"
    assert report.segments[-1].name == "Bus Stop 2"


def test_segment_best_vs_median_deltas_sum_to_lap_delta():
    report = analyze(synthetic_run())
    expected = report.median_time - report.best_time
    assert abs(sum(segment.gain_vs_median_s for segment in report.segments) - expected) < 0.01
    assert all(segment.potential_gain_s >= 0 for segment in report.segments)


def test_incident_lap_is_marked_and_remains_valid():
    run = synthetic_run()
    mask = (run.samples["lap"] == 2) & (run.samples["lap_dist_pct"] >= 0.4)
    run.samples["incidents"][mask] = 1
    run.samples["track_surface"][mask & (run.samples["lap_dist_pct"] < 0.41)] = 0
    report = analyze(run)
    lap = next(item for item in report.laps if item.number == 2)
    assert lap.valid
    assert lap.incident_points == 1
    assert "incident_1x" in lap.badges
    assert lap.incident_events[0].likely_off_track
    assert report.track_map.incidents


def test_pair_comparison_rejects_self_and_has_unique_insights():
    run = synthetic_run()
    comparison = compare_laps(run, 1, 3)
    assert comparison.selected_lap == 1
    assert comparison.reference_lap == 3
    assert len(comparison.telemetry.distance_pct) == 1200
    assert len({item.segment_id for item in comparison.insights}) == len(comparison.insights)
    assert [item.rank for item in comparison.insights] == list(range(1, len(comparison.insights) + 1))
    try:
        compare_laps(run, 1, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("self-comparison must fail")


def test_out_lap_and_terminal_fragment_are_reported_but_excluded():
    run = synthetic_run(3)
    prefix = 180
    suffix = 240
    samples = {}
    for key, values in run.samples.items():
        values = np.asarray(values)
        first = values[:prefix].copy()
        last = values[-suffix:].copy()
        if key == "lap":
            first[:] = 0
            last[:] = 4
        elif key == "lap_dist_pct":
            first[:] = np.linspace(0, 0.15, prefix, endpoint=False)
            last[:] = np.linspace(0, 0.2, suffix, endpoint=False)
        elif key == "on_pit_road":
            first[:60] = 1
        elif key == "session_time":
            first[:] = np.linspace(-3, -0.01, prefix)
            last[:] = np.linspace(values[-1] + 0.01, values[-1] + 4, suffix)
        samples[key] = np.concatenate([first, values, last])
    run.samples = samples
    report = analyze(run)
    out_lap = next(lap for lap in report.laps if lap.number == 0)
    incomplete = next(lap for lap in report.laps if lap.number == 4)
    assert out_lap.display_type == "out_lap"
    assert "out_lap" in out_lap.badges
    assert not out_lap.valid
    assert incomplete.display_type == "incomplete"
    assert "incomplete" in incomplete.badges
    assert not incomplete.valid
    assert report.data_sufficiency.valid_laps == 3
