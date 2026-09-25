"""The Auto rule picks a predictor from its record on *earlier* races only - it drives what the
app shows live, so it must be as leak-free as the predictors themselves."""
import numpy as np
import pandas as pd

from f1cc import backtest_summary as bts


def _bt(n_rounds=8, better_from=4):
    """Ridge worse than the baseline early, better from ``better_from`` on."""
    rows = []
    for r in range(1, n_rounds + 1):
        for k in (1, 4):
            rows.append({"round": r, "stage": k, "predictor": bts.BASELINE, "spearman": 0.60})
            rows.append({"round": r, "stage": k, "predictor": "Ridge", "spearman": 0.50 if r < better_from else 0.90})
    return pd.DataFrame(rows)


def test_baseline_until_enough_races():
    bt = _bt()
    for r in range(1, bts.MIN_RACES + 1):
        assert bts.pick(bt, r, 4) == bts.BASELINE


def test_switches_once_the_record_says_so():
    bt = _bt(n_rounds=12, better_from=4)
    picks = [bts.pick(bt, r, 4) for r in range(1, 13)]
    assert picks[3] == bts.BASELINE          # after races 1-3 ridge has only been worse
    assert picks[-1] == "Ridge"              # by race 12 its later record dominates


def test_never_looks_at_the_race_or_later_races():
    bt = _bt()
    scrambled = bt.copy()
    later = scrambled["round"] >= 6
    scrambled.loc[later, "spearman"] = np.random.default_rng(0).uniform(-1, 1, later.sum())
    assert [bts.pick(bt, 6, k) for k in (1, 4)] == [bts.pick(scrambled, 6, k) for k in (1, 4)]


def test_with_auto_adds_one_row_per_race_and_stage():
    bt = _bt()
    full = bts.with_auto(bt)
    auto = full[full["predictor"] == bts.AUTO]
    assert len(auto) == bt[["round", "stage"]].drop_duplicates().shape[0]
    assert len(bts.with_auto(full)) == len(full)                 # idempotent
