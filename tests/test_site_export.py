"""The website export: same numbers as the stored tables, and no race result in a replay file."""
import json

import numpy as np
import pandas as pd
import pytest

from f1cc import commentary, site_export, store

YEAR = site_export.SITE_YEAR


@pytest.fixture(scope="module")
def stored():
    tables = {t: store.read(t, [YEAR]) for t in store.TABLES}
    if tables["features"].empty:
        pytest.skip("no stored data")
    return tables, store.read("predictions", [YEAR]), store.read("backtest", [YEAR])


def _finished_round(features: pd.DataFrame) -> int:
    race = features[(features["session"] == "Race") & features["position"].notna()]
    return int(race["round"].max())


def test_replay_file_never_depends_on_the_race(stored):
    tables, preds, bt = stored
    rd = _finished_round(tables["features"])
    before = site_export.build_weekend(tables, preds, bt, YEAR, rd, {}, False, {})
    f = tables["features"].copy()
    race = (f["round"] == rd) & (f["session"] == "Race")
    f.loc[race, "position"] = f.loc[race, "position"][::-1].to_numpy()      # scramble the result
    f.loc[race, "status"] = "Retired"
    after = site_export.build_weekend({**tables, "features": f}, preds, bt, YEAR, rd, {}, False, {})
    assert json.dumps(before) == json.dumps(after)
    assert "Race" not in {s["session"] for s in before["steps"]}


def test_prediction_numbers_match_the_stored_predictions(stored):
    tables, preds, bt = stored
    rd = _finished_round(tables["features"])
    wk = site_export.build_weekend(tables, preds, bt, YEAR, rd, {}, False, {})
    last = wk["steps"][-1]
    who = last["prediction"]["auto"]
    src = preds[(preds["round"] == rd) & (preds["stage"] == last["stage"]) & (preds["predictor"] == who)]
    src = src.set_index("driver")
    for row in last["prediction"]["by"][who]:
        s = src.loc[row["driver"]]
        assert row["pos"] == int(s["expected_pos"])
        assert row["p_win"] == pytest.approx(s["p_win"], abs=1e-4)
        assert row["p_podium"] == pytest.approx(s["p_podium"], abs=1e-4)
        assert row["lo"] <= row["pos"] + 1 and row["hi"] >= 1
        assert 0 <= row["p_points"] <= 1
    assert sum(r["p_win"] for r in last["prediction"]["by"][who]) == pytest.approx(1, abs=0.01)


def test_race_file_matches_backtest_scores(stored):
    tables, preds, bt = stored
    rd = _finished_round(tables["features"])
    race = site_export.build_race(tables["features"], preds, bt, YEAR, rd, {})
    b = bt[(bt["round"] == rd) & (bt["stage"] == 4)].set_index("predictor")
    for who, s in race["scores"]["4"].items():
        if who in b.index:
            assert s["spearman"] == pytest.approx(b.loc[who, "spearman"], abs=1e-4)
    assert [r["pos"] for r in race["result"]] == sorted(r["pos"] for r in race["result"])


def test_json_is_strict(stored, tmp_path):
    tables, preds, bt = stored
    rd = _finished_round(tables["features"])
    wk = site_export.build_weekend(tables, preds, bt, YEAR, rd, {}, False, {})
    site_export.write_json(tmp_path / "w.json", wk)       # allow_nan=False: raises on NaN
    assert json.loads((tmp_path / "w.json").read_text())["round"] == rd


def test_likely_range_covers_80_percent():
    dist = np.array([0.05, 0.1, 0.5, 0.2, 0.1, 0.05])
    assert site_export._range(dist) == (2, 5)


def test_commentary_articles():
    assert commentary.a_pct(0.863) == "an 86.3%"
    assert commentary.a_pct(0.454) == "a 45.4%"
    assert commentary.a_pct(0.11) == "an 11.0%"


# --- the accuracy and home pages must follow the data, never a stale snapshot -----------------

def _published(name: str) -> dict:
    p = store.ROOT / "web" / "data" / f"{name}.json"
    if not p.exists():
        pytest.skip("run scripts/export_site.py first")
    return json.loads(p.read_text())


def test_published_accuracy_matches_the_stored_backtest(stored):
    """What the Accuracy page shows is exactly what the current backtest says."""
    _, _, bt = stored
    fresh = site_export.build_accuracy(bt)
    live = _published("accuracy")
    key = lambda s: (s["stage"], s["predictor"])                                  # noqa: E731
    assert {key(s): s for s in live["summary"]} == {key(s): s for s in fresh["summary"]}
    assert len(live["per_round"]) == len(fresh["per_round"])


def test_published_season_covers_every_stored_round(stored):
    """The home page's calendar and headline numbers follow the stored rounds."""
    tables, _, _ = stored
    live = _published("season")
    assert {r["round"] for r in live["rounds"]} >= set(tables["features"]["round"])
    raced = set(tables["features"].loc[tables["features"]["session"] == "Race", "round"])
    assert {r["round"] for r in live["rounds"] if r["status"] == "finished"} == raced


def test_a_new_race_moves_the_accuracy_numbers(stored):
    """Adding a race to the backtest changes what the pages report: the numbers are derived on
    every export, so the model learning from a new result cannot leave a stale page behind."""
    _, _, bt = stored
    before = site_export.build_accuracy(bt)
    extra = bt[bt["round"] == bt["round"].max()].copy()
    extra["round"] += 1
    extra["spearman"] = 0.0                       # a hypothetical terrible weekend
    extra["mae_pos"] = 9.0
    after = site_export.build_accuracy(pd.concat([bt, extra], ignore_index=True))
    pick = lambda a: next(s for s in a["summary"]                                  # noqa: E731
                          if s["stage"] == 4 and s["predictor"] == a["baseline"])
    assert pick(after)["races"] == pick(before)["races"] + 1
    assert pick(after)["spearman"] < pick(before)["spearman"]
    assert pick(after)["mae"] > pick(before)["mae"]


# --- the starting grid: real when known, qualifying order clearly labelled while pending -------

def test_grid_is_official_once_the_race_has_run(stored):
    tables, preds, bt = stored
    rd = _finished_round(tables["features"])
    q = site_export.build_weekend(tables, preds, bt, YEAR, rd, {}, False, {})["steps"][-1]
    assert q["grid_state"] == "official"
    assert sorted(g["grid"] for g in q["grid"] if g["grid"]) == list(range(1, sum(1 for g in q["grid"] if g["grid"]) + 1))


def test_grid_falls_back_to_qualifying_order_while_the_race_is_pending(stored):
    """A live weekend has no official grid: penalties are published as stewards' documents, not in
    the timing data. Show qualifying order, flagged, rather than nothing."""
    tables, preds, bt = stored
    f = tables["features"]
    rd = next((r for r in sorted(set(f["round"]), reverse=True)
               if store.starting_grid(f[f["session"] != "Race"], YEAR, r).empty), None)
    if rd is None:
        pytest.skip("every stored round has a hand-entered grid")
    pending = f[~((f["round"] == rd) & (f["session"] == "Race"))]
    q = site_export.build_weekend({**tables, "features": pending}, preds, bt, YEAR, rd, {}, True, {})["steps"][-1]
    assert q["grid_state"] == "provisional"
    order = [g["driver"] for g in sorted(q["grid"], key=lambda g: g["grid"])]
    # Only drivers who actually set a qualifying time get a slot - a driver who didn't (and so
    # starts from the back or the pit lane) is left out rather than given an invented position.
    sheet = [t["driver"] for t in q["timesheet"] if t["driver"] in set(order)]
    assert order == sheet
    assert [g["grid"] for g in sorted(q["grid"], key=lambda g: g["grid"])] == list(range(1, len(order) + 1))
    assert all(g["penalty"] is None for g in q["grid"])      # a penalty is never invented
