"""Summarise data/backtest_*.parquet: mean metrics per stage and a paired bootstrap over races
for the model-minus-baseline difference (races, not drivers, are the independent units)."""
from __future__ import annotations

import numpy as np
import pandas as pd

BASELINE = "Baseline (grid, else practice pace)"
METRICS = ["spearman", "top3_overlap", "winner_hit", "mae_pos", "winner_logloss", "podium_brier", "rps"]
LOWER_IS_BETTER = {"mae_pos", "winner_logloss", "podium_brier", "rps"}


def summarize(bt: pd.DataFrame) -> pd.DataFrame:
    """Stage = how many sessions were revealed (1-4). On sprint weekends stages 2-3 are Sprint
    Qualifying / Sprint rather than Practice 2 / 3; stage 4 is always Qualifying."""
    return bt.groupby(["stage", "predictor"])[METRICS].mean().reset_index()


def paired_diff(bt: pd.DataFrame, predictor: str, metric: str = "spearman", n_boot: int = 4000,
                seed: int = 0) -> pd.DataFrame:
    """Per stage: mean(predictor - baseline) over races, with a 95% bootstrap interval."""
    rng = np.random.default_rng(seed)
    rows = []
    for stage, g in bt.groupby("stage"):
        wide = g.pivot(index="round", columns="predictor", values=metric).dropna()
        if predictor not in wide or BASELINE not in wide or wide.empty:
            continue
        d = (wide[predictor] - wide[BASELINE]).to_numpy()
        boots = rng.choice(d, size=(n_boot, len(d))).mean(axis=1)
        lo, hi = np.percentile(boots, [2.5, 97.5])
        rows.append({"stage": stage, "races": len(d), "diff": d.mean(), "lo": lo, "hi": hi,
                     "significant": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(rows)


# --- choosing a predictor by its record this season --------------------------------------
AUTO = "Auto (best record this season)"
MIN_RACES = 3              # before this many races, trust the baseline


def pick(bt: pd.DataFrame, round_number: int, stage: int, min_races: int = MIN_RACES) -> str:
    """The predictor with the best mean Spearman on this season's races *before* ``round_number``
    at the same stage; the baseline until ``min_races`` races exist. Uses only finished races, so
    it can drive live predictions without leaking. Re-decided every race, so a model that starts a
    new-rules season badly can earn its place later."""
    prev = bt[(bt["round"] < round_number) & (bt["stage"] == stage) & (bt["predictor"] != AUTO)]
    if prev["round"].nunique() < min_races:
        return BASELINE
    return str(prev.groupby("predictor")["spearman"].mean().idxmax())


def with_auto(bt: pd.DataFrame) -> pd.DataFrame:
    """``bt`` plus rows for the Auto rule: for every race and stage, the chosen predictor's row."""
    bt = bt[bt["predictor"] != AUTO]
    picked = [bt[(bt["round"] == r) & (bt["stage"] == k) & (bt["predictor"] == pick(bt, r, k))]
              for r, k in bt[["round", "stage"]].drop_duplicates().itertuples(index=False)]
    return pd.concat([bt, pd.concat(picked).assign(predictor=AUTO)], ignore_index=True)


def season_trend(bt: pd.DataFrame, stage: int) -> pd.DataFrame:
    """Per round: each predictor's Spearman minus the baseline's, and the season-to-date mean of it."""
    w = bt[bt["stage"] == stage].pivot_table(index="round", columns="predictor", values="spearman")
    diff = w.drop(columns=BASELINE).sub(w[BASELINE], axis=0).sort_index()
    long = diff.reset_index().melt(id_vars="round", var_name="predictor", value_name="diff")
    long["to_date"] = long.groupby("predictor")["diff"].transform(lambda d: d.expanding().mean())
    return long

