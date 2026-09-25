"""Smoke test the Streamlit app end to end: replay a weekend to Qualifying, then open the race
view. The replay must never show race data; the race view must."""
import pytest

from f1cc import store

pytestmark = pytest.mark.skipif(not store.available_years("predictions"), reason="needs data/ and predictions")
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _replay_to_qualifying():
    at = AppTest.from_file("app.py", default_timeout=120).run()
    for _ in range(4):
        [b for b in at.button if "Next" in b.label][0].click().run()
    return at


def test_replay_shows_whole_grid_prediction_without_race_data():
    at = _replay_to_qualifying()
    assert not at.exception
    table = at.dataframe[0].value
    assert len(table) >= 20 and "p_win" in table and "session_pos" in table
    assert "actual" not in table and not any(m.label == "Winner" for m in at.metric)


def test_race_view_shows_result_next_to_prediction():
    at = _replay_to_qualifying()
    [r for r in at.sidebar.radio if r.label == "View"][0].set_value("Race result").run()
    assert not at.exception
    assert any(m.label == "Winner" for m in at.metric)
    table = at.dataframe[0].value
    assert {"actual", "expected_pos", "p_win"} <= set(table.columns) and len(table) >= 20
