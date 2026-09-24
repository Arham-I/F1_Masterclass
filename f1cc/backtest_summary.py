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
