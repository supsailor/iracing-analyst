import numpy as np

from iracing_analyst.analysis import analyze, normalize_laps, telemetry_for_laps
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

