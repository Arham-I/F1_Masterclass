"""Ridge regression on regime-neutral features (ranks, relative gaps, in-season form).

Trained on Race results of every weekend before the one being predicted - by default the earlier
seasons too, which is safe because no feature is an absolute lap time. One model per stage of
the weekend, since the available features differ. numpy-only: with ~2k rows and 8 features a
closed-form ridge is the right size of tool."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import FEATURES, FeatureBuilder, SimulatedPredictor, fill_for_model
from .baseline import BaselinePredictor

ALPHA = 10.0

# Inputs added once Qualifying is visible, per ridge flavour. Chosen on 2023-26 by whether they
# improved the second half of seasons (see docs/experiments.md): gains are small (~0.002-0.004
# Spearman) and the Auto rule still decides race by race whether ridge is used at all.
#   all seasons:  + gap to teammate in qualifying
#   same season:  + new soft sets used before the race, practice pace weighted FP1x1/FP2x2/FP3x3
AFTER_Q = {False: dict(extra=["tm_delta"], weighted_pace=False),
           True: dict(extra=["new_soft"], weighted_pace=True)}
MIN_ROWS = 40              # below this, no fit is better than a wild one: fall back to the baseline


class RidgePredictor(SimulatedPredictor):
    def __init__(self, features: pd.DataFrame | None, builder: FeatureBuilder | None = None,
                 same_year_only: bool = False, alpha: float = ALPHA):
        super().__init__(features, builder)
        self.same_year_only, self.alpha = same_year_only, alpha
        self.name = "Ridge (2026 only)" if same_year_only else "Ridge (all seasons)"
        self._rows: dict[tuple[int, int, int], tuple[pd.DataFrame, np.ndarray] | None] = {}

    def _training_rows(self, y: int, r: int, k: int):
        key = (y, r, k)
        if key not in self._rows:
            h = self.builder.matrix(y, r, k, with_target=True).dropna(subset=["actual"])
            self._rows[key] = (fill_for_model(h), h["actual"].to_numpy()) if len(h) >= 10 else None
        return self._rows[key]

    def _training(self, year: int, round_number: int, k: int) -> tuple[pd.DataFrame, np.ndarray]:
        rows = [self._training_rows(y, r, k) for (y, r) in self.builder.weekends_before(year, round_number)
                if not (self.same_year_only and y != year)]
        rows = [x for x in rows if x is not None]
        if not rows:
            return pd.DataFrame(columns=FEATURES), np.array([])
        return pd.concat([x for x, _ in rows], ignore_index=True), np.concatenate([t for _, t in rows])

    def feature_names(self, m: pd.DataFrame) -> list[str]:
        if m["q_pos"].isna().all():
            return list(FEATURES)
        cfg = AFTER_Q[self.same_year_only]
        base = [{"prac_rank": "prac_rank_w", "prac_gap_pct": "prac_gap_pct_w"}.get(c, c) if cfg["weighted_pace"] else c
                for c in FEATURES]
        return base + cfg["extra"]

    def _score(self, m: pd.DataFrame, year: int, round_number: int, k: int) -> np.ndarray:
        X, y = self._training(year, round_number, k)
        if len(y) < MIN_ROWS:
            return BaselinePredictor.score(m)
        cols = [c for c in self.feature_names(m) if X[c].notna().all() and X[c].std() > 0]
        mu, sd = X[cols].mean(), X[cols].std()
        Z = ((X[cols] - mu) / sd).to_numpy()
        coef = np.linalg.solve(Z.T @ Z + self.alpha * np.eye(len(cols)), Z.T @ (y - y.mean()))
        return y.mean() + ((fill_for_model(m)[cols] - mu) / sd).to_numpy() @ coef
