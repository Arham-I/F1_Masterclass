"""The yardstick: after Qualifying, finish where you start; before it, finish where practice
pace ranks you. No fitted parameters - only the noise level (sigma) is estimated, from earlier races."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..replay import Cutoff
from .base import FeatureBuilder, fill_for_model, simulate


class BaselinePredictor:
    name = "Baseline (grid, else practice pace)"

    def __init__(self, features: pd.DataFrame, builder: FeatureBuilder | None = None):
        self.builder = builder or FeatureBuilder(features)

    @staticmethod
    def score(m: pd.DataFrame) -> np.ndarray:
        x = fill_for_model(m)
        primary = x["q_pos"] if m["q_pos"].notna().any() else x["prac_rank"]
        return (primary + 1e-3 * x["prac_rank"]).to_numpy()      # practice pace breaks grid ties

    def _sigma(self, w, k: int) -> float:
        resid = []
        for (y, r) in self.builder.weekends_before(w.year, w.round)[-40:]:
            h = self.builder.matrix(y, r, k, with_target=True).dropna(subset=["actual"])
            if len(h) >= 10:
                s = self.score(h)
                resid.append(h["actual"].to_numpy() - s.argsort().argsort() - 1)
        return float(np.std(np.concatenate(resid))) if resid else 6.0

    def predict(self, cutoff: Cutoff) -> pd.DataFrame:
        w = cutoff.weekend
        m = self.builder.matrix(w.year, w.round, cutoff.revealed)
        if m.empty:
            return m.assign(score=[], expected_pos=[], p_win=[], p_podium=[], sigma=[])
        score = self.score(m)
        sigma = self._sigma(w, cutoff.revealed)
        p_win, p_pod = simulate(score, sigma)
        out = m[["driver", "team", "team_color"]].copy()
        out["score"], out["sigma"] = score, sigma
        out["expected_pos"] = score.argsort().argsort() + 1
        out["p_win"], out["p_podium"] = p_win, p_pod
        return out.sort_values("score").reset_index(drop=True)
