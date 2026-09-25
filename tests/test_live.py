"""A live weekend (sessions stored, race not run) is predicted but never scored, and only
sessions that have finished are pulled."""
import pandas as pd
import pytest

from f1cc import store
from f1cc.data import finished_sessions

ROW = pd.Series({"Session1": "Practice 1", "Session1DateUtc": pd.Timestamp("2026-09-24 08:30"),
                 "Session2": "Practice 2", "Session2DateUtc": pd.Timestamp("2026-09-24 12:00"),
                 "Session3": "Practice 3", "Session3DateUtc": pd.Timestamp("2026-09-25 08:30"),
                 "Session4": "Qualifying", "Session4DateUtc": pd.Timestamp("2026-09-25 12:00"),
                 "Session5": "Race", "Session5DateUtc": pd.Timestamp("2026-09-26 11:00")})


def test_only_finished_sessions_and_never_the_race():
    assert finished_sessions(ROW, pd.Timestamp("2026-09-24 09:00")) == []                 # FP1 still running
    assert finished_sessions(ROW, pd.Timestamp("2026-09-25 10:00")) == ["Practice 1", "Practice 2"]
    assert finished_sessions(ROW, pd.Timestamp("2026-09-25 14:30")) == ["Practice 1", "Practice 2",
                                                                         "Practice 3", "Qualifying"]
    assert "Race" not in finished_sessions(ROW, pd.Timestamp("2027-01-01"))            # even long after


@pytest.mark.skipif(not store.available_years("predictions"), reason="run scripts/backtest.py first")
def test_live_weekend_is_predicted_but_not_scored():
    f = store.read("features", [2026])
    live = set(f["round"]) - set(f.loc[f["session"] == "Race", "round"])
    if not live:
        pytest.skip("no live weekend stored")
    preds, bt = store.read("predictions", [2026]), store.read("backtest", [2026])
    for r in live:
        assert (preds["round"] == r).any()
        assert not (bt["round"] == r).any()
