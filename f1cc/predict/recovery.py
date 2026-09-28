"""Grid + recovery: the baseline's grid order, with fast cars that start out of position expected
to move forward.

A car's pace slot is the field rank of the mean of three estimates of where it belongs: practice
pace rank, the teammate's qualifying position, and the team's race pace in this season's earlier
races. A driver starting behind that slot is moved up by gamma x ease x the gap (never down), where
ease is the circuit's on-track overtaking rate relative to average from earlier races (Monaco ~0.4,
Las Vegas ~1.5; FeatureBuilder.track_ease). gamma is chosen before every race on *all* earlier races.

Evidence (docs/experiments.md): over 2023-26 +0.017 Spearman after Qualifying
(interval above zero); in 2026 neutral so far (-0.002), where qualifying has been unusually
decisive. Re-tuning gamma from only this season or the last few races did worse. The Auto rule
decides race by race whether this predictor is used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import FeatureBuilder, fill_for_model
from .baseline import TIME_WEIGHT, BaselinePredictor

GAMMAS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7)


def pace_slot(m: pd.DataFrame) -> np.ndarray:
    """Field rank of where each car's pace says it belongs (1 = fastest). Uses whatever of the
    three estimates exist for that driver; a driver with none keeps his grid slot."""
    est = pd.DataFrame({"prac": m["prac_rank"].rank(),
                        "mate": m["tm_q_pos"],
                        "race": m["team_race_pace"].rank()})
    slot = est.mean(axis=1).rank(method="first")
    return slot.fillna(m["q_pos"]).to_numpy(dtype=float)


def recovery_shift(m: pd.DataFrame, gamma: float) -> np.ndarray:
    """Places each driver is moved forward (>= 0). Zero before Qualifying is visible."""
    if m["q_pos"].isna().all() or gamma == 0:
        return np.zeros(len(m))
    q = fill_for_model(m)["q_pos"].to_numpy(dtype=float)
    return gamma * np.maximum(0.0, q - pace_slot(m))


class RecoveryPredictor(BaselinePredictor):
    name = "Grid + recovery"

    def __init__(self, features, builder: FeatureBuilder | None = None):
        super().__init__(features, builder)
        self._rho: dict[tuple[int, int], dict[float, float]] = {}
        self._gamma: dict[tuple[int, int], float] = {}

    def _race_scores(self, y: int, r: int) -> dict[float, float]:
        """Spearman of the recovery-adjusted grid with the real finish, per gamma, for one
        finished weekend (at its first stage with Qualifying visible)."""
        if (y, r) not in self._rho:
            w = self.builder.weekend(y, r)
            k = w.replayable.index("Qualifying") + 1 if "Qualifying" in w.replayable else None
            out = {}
            if k is not None:
                m = self.builder.matrix(y, r, k)
                act = m["driver"].map(self.builder.result(y, r).set_index("driver")["position"])
                ok = act.notna().to_numpy()
                if ok.sum() >= 10:
                    q = fill_for_model(m)["q_pos"].to_numpy(dtype=float)
                    ease = self.builder.track_ease(y, r)
                    for g in GAMMAS:
                        adj = pd.Series(q - recovery_shift(m, g * ease))[ok]
                        out[g] = adj.rank(method="first").corr(act[ok].rank())
            self._rho[(y, r)] = out
        return self._rho[(y, r)]

    def gamma(self, year: int, round_number: int) -> float:
        key = (year, round_number)
        if key not in self._gamma:
            scores = [self._race_scores(y, r) for (y, r) in self.builder.weekends_before(year, round_number)]
            scores = [s for s in scores if s]
            self._gamma[key] = (max(GAMMAS, key=lambda g: np.mean([s[g] for s in scores]))
                                if len(scores) >= 10 else 0.0)
        return self._gamma[key]

    def _score(self, m: pd.DataFrame, year: int = 0, round_number: int = 0, k: int = 0) -> np.ndarray:
        base = super()._score(m, year, round_number, k)
        return base - recovery_shift(m, self.strength(year, round_number))

    def _center(self, m, place, year, round_number, k) -> np.ndarray:
        # The baseline's time-scale centre, moved forward by the same recovery shift.
        base_place = pd.Series(BaselinePredictor.score(m)).rank(method="first").to_numpy()
        center = super()._center(m, base_place, year, round_number, k)
        return center - recovery_shift(m, self.strength(year, round_number))

    def strength(self, year: int, round_number: int) -> float:
        """gamma scaled by how easy this circuit is to pass on (Monaco ~0.4x, Las Vegas ~1.5x)."""
        return self.gamma(year, round_number) * self.builder.track_ease(year, round_number)
