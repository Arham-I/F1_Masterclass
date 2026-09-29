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
    assert finished_sessions(ROW, pd.Timestamp("2026-09-25 09:55")) == ["Practice 1", "Practice 2"]
    assert finished_sessions(ROW, pd.Timestamp("2026-09-25 14:30")) == ["Practice 1", "Practice 2",
                                                                         "Practice 3", "Qualifying"]
    assert "Race" not in finished_sessions(ROW, pd.Timestamp("2027-01-01"))            # even long after


def test_a_session_is_due_30_minutes_after_it_ends():
    """FP1 runs 08:30-09:30, so it is due at 10:00 and not a minute before."""
    assert finished_sessions(ROW, pd.Timestamp("2026-09-24 09:59")) == []
    assert finished_sessions(ROW, pd.Timestamp("2026-09-24 10:00")) == ["Practice 1"]


def test_race_is_due_only_for_the_scheduler_and_waits_longer():
    """The race runs 11:00-13:15 (135 min allowed), so it is due at 14:15, an hour after."""
    late = pd.Timestamp("2026-09-26 14:15")
    assert finished_sessions(ROW, late) == ["Practice 1", "Practice 2", "Practice 3", "Qualifying"]
    assert finished_sessions(ROW, pd.Timestamp("2026-09-26 14:14"), include_race=True)[-1] == "Qualifying"
    assert finished_sessions(ROW, late, include_race=True)[-1] == "Race"


def test_sprint_sessions_have_their_own_lengths():
    sprint = pd.Series({"Session1": "Sprint", "Session1DateUtc": pd.Timestamp("2026-03-14 03:00")})
    assert finished_sessions(sprint, pd.Timestamp("2026-03-14 04:14")) == []       # 45 min + 30
    assert finished_sessions(sprint, pd.Timestamp("2026-03-14 04:15")) == ["Sprint"]


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


def test_hand_entered_starting_grids_are_complete_and_consistent():
    """Every hand-entered grid: positions 1..n once each, drivers = that weekend's qualifiers."""
    if not store.GRID_FILE.exists():
        pytest.skip("no starting_grid.csv")
    g = pd.read_csv(store.GRID_FILE)
    f = store.read("features")
    for (y, r), grid in g.groupby(["year", "round"]):
        assert sorted(grid["grid"]) == list(range(1, len(grid) + 1)), f"{y} R{r}: grid slots"
        quali = f[(f["year"] == y) & (f["round"] == r) & (f["session"] == "Qualifying")]["driver"]
        assert set(grid["driver"]) == set(quali), f"{y} R{r}: drivers differ from qualifying"
        assert grid["penalty"].notna().sum() >= 1 or (grid["grid"].values == range(1, len(grid) + 1)).all()


def test_starting_grid_prefers_the_stored_race():
    f = store.read("features", [2026])
    g = store.starting_grid(f, 2026, 14)                    # a finished weekend: from the Race rows
    race = f[(f["round"] == 14) & (f["session"] == "Race")]
    assert len(g) == len(race) and g["penalty"].isna().all()
