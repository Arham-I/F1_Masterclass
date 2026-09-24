"""Ridge regression on regime-neutral features (ranks, relative gaps, in-season form).

Trained on Race results of every weekend before the one being predicted - by default the earlier
seasons too, which is safe because no feature is an absolute lap time. One model per stage of
the weekend, since the available features differ. numpy-only: with ~2k rows and 7 features a
closed-form ridge is the right size of tool."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..replay import Cutoff
from .base import FEATURES, FeatureBuilder, fill_for_model, simulate

ALPHA = 10.0


class RidgePredictor:
    def __init__(self, features: pd.DataFrame, builder: FeatureBuilder | None = None,
                 same_year_only: bool = False, alpha: float = ALPHA):
        self.builder = builder or FeatureBuilder(features)
        self.same_year_only, self.alpha = same_year_only, alpha
        self.name = "Ridge (2026 only)" if same_year_only else "Ridge (all seasons)"

    def _training(self, w, k: int) -> tuple[pd.DataFrame, np.ndarray]:
        xs, ys = [], []
        for (y, r) in self.builder.weekends_before(w.year, w.round):
            if self.same_year_only and y != w.year:
                continue
            h = self.builder.matrix(y, r, k, with_target=True).dropna(subset=["actual"])
            if len(h) >= 10:
                xs.append(fill_for_model(h))
                ys.append(h["actual"].to_numpy())
        if not xs:
            return pd.DataFrame(columns=FEATURES), np.array([])
        return pd.concat(xs, ignore_index=True), np.concatenate(ys)

    def _fit(self, X: pd.DataFrame, y: np.ndarray):
        cols = [c for c in FEATURES if X[c].notna().all() and X[c].std() > 0]
        mu, sd = X[cols].mean(), X[cols].std()
        Z = ((X[cols] - mu) / sd).to_numpy()
        b = y.mean()
        coef = np.linalg.solve(Z.T @ Z + self.alpha * np.eye(len(cols)), Z.T @ (y - b))
        resid = y - (b + Z @ coef)
        return cols, mu, sd, b, coef, float(resid.std())

    def predict(self, cutoff: Cutoff) -> pd.DataFrame:
        w, k = cutoff.weekend, cutoff.revealed
        m = self.builder.matrix(w.year, w.round, k)
        if m.empty:
            return m.assign(score=[], expected_pos=[], p_win=[], p_podium=[], sigma=[])
        X, y = self._training(w, k)
        if len(y) < 40:                       # too little history: no fit is better than a wild one
            from .baseline import BaselinePredictor
            return BaselinePredictor(None, self.builder).predict(cutoff)
        cols, mu, sd, b, coef, sigma = self._fit(X, y)
        Z = ((fill_for_model(m)[cols] - mu) / sd).to_numpy()
        score = b + Z @ coef
        p_win, p_pod = simulate(score, sigma)
        out = m[["driver", "team", "team_color"]].copy()
        out["score"], out["sigma"] = score, sigma
        out["expected_pos"] = score.argsort().argsort() + 1
        out["p_win"], out["p_podium"] = p_win, p_pod
        return out.sort_values("score").reset_index(drop=True)
