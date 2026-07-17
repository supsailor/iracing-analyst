from iracing_analyst.fixture import synthetic_run
from iracing_analyst.storage import SessionStore


def test_round_trip(tmp_path):
    store = SessionStore(tmp_path)
    report = store.add(synthetic_run(), "fixture")
    assert store.report(report.session_id) == report
    assert store.run(report.session_id) is not None
    assert store.list()[0].id == report.session_id

