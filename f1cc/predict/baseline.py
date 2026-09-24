"""The yardstick: finish in the most recent competitive order. After Qualifying that is the
qualifying order; on a sprint weekend before it, the sprint sessions' order; otherwise practice
pace. No fitted parameters - only the noise is estimated, from its own errors on earlier races."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .base import SimulatedPredictor, fill_for_model


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
