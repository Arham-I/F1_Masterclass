"""Expanding-window backtest on 2026: each race is predicted using only what was knowable at
that cutoff (its own revealed sessions + Race results of earlier weekends), never a random split.

Writes data/backtest.parquet (one row per race x stage x predictor: metrics) and
data/predictions_2026.parquet (per-driver predictions the app displays).
Usage: python scripts/backtest.py [--year 2026]
"""
import argparse
import warnings

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from f1cc import store
from f1cc.predict import BaselinePredictor, FeatureBuilder, RidgePredictor
from f1cc.predict.base import rps
from f1cc.replay import Cutoff

warnings.filterwarnings("ignore")
STAGES = (1, 2, 3, 4)


def metrics(pred: pd.DataFrame, actual: pd.Series) -> dict:
    p = pred.assign(actual=pred["driver"].map(actual)).dropna(subset=["actual"])
    dist = np.stack(p["p_pos"].to_numpy())
    winner = p.loc[p["actual"].idxmin()]
    top3_actual = set(p.nsmallest(3, "actual")["driver"])
    top3_pred = set(p.nsmallest(3, "score")["driver"])
    return {
        "n": len(p),
        "spearman": spearmanr(p["score"], p["actual"])[0],
        "winner_hit": float(p.loc[p["score"].idxmin(), "driver"] == winner["driver"]),
        "top3_overlap": len(top3_actual & top3_pred) / 3,
        "mae_pos": float((p["expected_pos"] - p["actual"]).abs().mean()),
        "winner_logloss": float(-np.log(max(winner["p_win"], 1e-4))),
        "podium_brier": float(((p["p_podium"] - (p["actual"] <= 3)) ** 2).mean()),
        "rps": rps(dist, p["actual"].rank(method="first").to_numpy()),
    }


def main(year: int):
    features = store.read("features")
    b = FeatureBuilder(features)
    predictors = [BaselinePredictor(features, b), RidgePredictor(features, b),
                  RidgePredictor(features, b, same_year_only=True)]
    rounds = sorted(features[(features["year"] == year) & (features["session"] == "Race")]["round"].unique())
    rows, preds = [], []
    for r in rounds:
        w = b.weekend(year, int(r))
        # Score against everyone who raced - not the FP1 entry list, which misses race drivers
        # replaced by a rookie in FP1 (and would drop the winner if it was one of them).
        actual = b.result(year, int(r)).set_index("driver")["position"]
        for k in STAGES:
            if k > len(w.replayable):
                continue
            for P in predictors:
                out = P.predict(Cutoff(w, k))
                rows.append({"year": year, "round": int(r), "stage": k, "stage_name": w.replayable[k - 1],
                             "predictor": P.name, **metrics(out, actual)})
                preds.append(out.assign(year=year, round=int(r), stage=k, predictor=P.name))
        print(f"R{int(r):02d} done", flush=True)
    store.write("backtest", year, pd.DataFrame(rows))
    store.write("predictions", year, pd.concat(preds, ignore_index=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2026)
    main(ap.parse_args().year)
