"""The yardstick: finish in the most recent competitive order. After Qualifying that is the
qualifying order; on a sprint weekend before it, the sprint sessions' order; otherwise practice
pace. No fitted parameters for the order - only the noise is estimated, from its own errors on
earlier races."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import ERROR_WINDOW, SimulatedPredictor, fill_for_model

# How much qualifying time gaps count vs grid places (0 = places only, 1 = time gaps only).
# Fixed, chosen on 2022-2025 races only: 0.5 was best on whole-grid RPS (0.1145 vs 0.1150 at 0)
# and podium Brier, and within 0.005 of best on winner log-loss, so 2026 is an unseen test.
# (Choosing it race by race from a 40-weekend window flipped on noise: RPS is nearly flat in it.)
TIME_WEIGHT = 0.5


class BaselinePredictor(SimulatedPredictor):
    name = "Baseline (grid, else practice pace)"
    use_sprint = True

    def _score(self, m: pd.DataFrame, year: int = 0, round_number: int = 0, k: int = 0) -> np.ndarray:
        return self.score(m, self.use_sprint)

    @staticmethod
    def score(m: pd.DataFrame, use_sprint: bool = True) -> np.ndarray:
        x = fill_for_model(m)
        if m["q_pos"].notna().any():
            primary = x["q_pos"]
        elif use_sprint and m["sprint_rank"].notna().any():
            primary = x["sprint_rank"]
        else:
            primary = x["prac_rank"]
        return (primary + 1e-3 * x["prac_rank"]).to_numpy()      # practice pace breaks ties

    # --- time scale ---------------------------------------------------------------------
    # Grid places are evenly spaced; lap times are not. Two cars 0.001s apart are a coin flip,
    # two cars 0.5s apart are not. Once Qualifying is visible, each car sits in the simulation
    # between its grid place and its qualifying gap converted to places. The predicted order
    # (expected_pos) is unchanged; only how often neighbours swap in the simulation changes. (Gaps
    # use each driver's best lap in any segment, which can disagree slightly with the knockout
    # classification - e.g. a Q1 lap faster than a Q2 one after the track rubbered in.)

    def _gaps(self, m: pd.DataFrame) -> np.ndarray | None:
        """Qualifying gap to pole in %, or None before Qualifying is visible."""
        if m["q_pos"].isna().all() or m["q_gap_pct"].isna().all():
            return None
        gap = m["q_gap_pct"].to_numpy(dtype=float) * 100
        return np.where(np.isnan(gap), np.nanmax(gap) * 1.1, gap)   # no time set: slowest of all

    def _pct_per_place(self, year: int, round_number: int, k: int) -> float:
        """Typical gap per grid place (gap at P10 / 9) over earlier weekends."""
        vals = []
        for (y, r) in self.builder.weekends_before(year, round_number)[-ERROR_WINDOW:]:
            gap = self._gaps(self.builder.matrix(y, r, k))
            if gap is not None and len(gap) >= 10:
                vals.append(np.sort(gap)[9] / 9)
        return float(np.median(vals)) if vals else 0.1

    def _time_center(self, m, place, weight, year, round_number, k) -> np.ndarray:
        gap = self._gaps(m)
        if gap is None or weight == 0:
            return place
        on_time_scale = 1 + gap / self._pct_per_place(year, round_number, k)
        return (1 - weight) * place + weight * on_time_scale

    def _center(self, m, place, year, round_number, k) -> np.ndarray:
        if self._gaps(m) is None:
            return place
        return self._time_center(m, place, TIME_WEIGHT, year, round_number, k)
