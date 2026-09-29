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
