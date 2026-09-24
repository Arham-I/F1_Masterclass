"""Shared plumbing for predictors: leak-safe feature matrices and win/podium probabilities.

A predictor answers one question: given a weekend and a cutoff, how will the Race finish?
Everything it may know comes from exactly two places:

* the weekend's own sessions that ``apply_cutoff`` reveals (never the Race), and
* Race results of weekends that finished *strictly before* this one (form + training data).

``FeatureBuilder.matrix`` is the only door to the data and enforces both rules, so predictors
built on it cannot leak, and the backtest is fair by construction.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

from ..replay import Cutoff, Weekend, apply_cutoff

PRIOR_POS = 10.5           # mean finishing position of a 20-car field: what "no history" means
TEAM_SHRINK = 4.0          # pseudo-observations of PRIOR_POS mixed into a team's form (2 cars/race)
DRIVER_SHRINK = 2.0
FEATURES = ["prac_rank", "prac_gap_pct", "lr_rank", "q_pos", "q_gap_pct", "team_form", "driver_form"]


class Predictor(Protocol):
    name: str

    def predict(self, cutoff: Cutoff) -> pd.DataFrame:
        """Columns: driver, team, team_color, score, expected_pos, p_win, p_podium, sigma."""


def simulate(score: np.ndarray, sigma: float, n: int = 20000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Win and podium probabilities: lower score finishes ahead; noise of size ``sigma`` (in
    finishing places) is added to every driver and the field is re-ranked ``n`` times."""
    rng = np.random.default_rng(seed)
    sim = score[None, :] + sigma * rng.standard_normal((n, len(score)))
    rank = sim.argsort(axis=1).argsort(axis=1)
    return (rank == 0).mean(axis=0), (rank < 3).mean(axis=0)


def _is_before(df: pd.DataFrame, year: int, round_number: int) -> pd.Series:
    return (df["year"] < year) | ((df["year"] == year) & (df["round"] < round_number))


class FeatureBuilder:
    """Turns the features table into one row per driver for (year, round, k sessions revealed)."""

    def __init__(self, features: pd.DataFrame):
        self.features = features
        self._races = (features[features["session"] == "Race"]
                       [["year", "round", "driver", "team", "position"]].dropna(subset=["position"]))
        self._weekends: dict[tuple[int, int], Weekend] = {}
        self._cache: dict[tuple[int, int, int], pd.DataFrame] = {}

    def weekend(self, year: int, round_number: int) -> Weekend:
        key = (year, round_number)
        if key not in self._weekends:
            self._weekends[key] = Weekend.from_features(self.features, year, round_number)
        return self._weekends[key]

    def weekends_before(self, year: int, round_number: int) -> list[tuple[int, int]]:
        keys = self._races[["year", "round"]].drop_duplicates()
        keys = keys[_is_before(keys, year, round_number)]
        return sorted(map(tuple, keys.to_numpy().tolist()))

    def matrix(self, year: int, round_number: int, k: int, with_target: bool = False) -> pd.DataFrame:
        key = (year, round_number, k)
        if key not in self._cache:
            self._cache[key] = self._build(year, round_number, k)
        m = self._cache[key]
        if not with_target:
            return m
        actual = (self._races[(self._races["year"] == year) & (self._races["round"] == round_number)]
                  .set_index("driver")["position"])
        return m.assign(actual=m["driver"].map(actual))

    def _build(self, year: int, round_number: int, k: int) -> pd.DataFrame:
        cutoff = Cutoff(self.weekend(year, round_number), k)
        vis = apply_cutoff(self.features, cutoff)          # the ONLY rows of this weekend we touch
        if vis.empty:
            return pd.DataFrame(columns=["driver", "team", "team_color", *FEATURES])

        practice = vis[vis["session"].str.startswith("Practice")].copy()
        practice["gap_pct"] = practice["gap_to_best_s"] / (practice["best_lap_s"] - practice["gap_to_best_s"])
        quali = vis[vis["session"] == "Qualifying"]

        last = vis.sort_values("session_idx").groupby("driver").last()
        out = pd.DataFrame({"driver": last.index, "team": last["team"].to_numpy(),
                            "team_color": last["team_color"].to_numpy()}).set_index("driver")
        out["prac_rank"] = practice.groupby("driver")["pace_rank"].mean()
        out["prac_gap_pct"] = practice.groupby("driver")["gap_pct"].mean()
        out["lr_rank"] = practice.groupby("driver")["longrun_rank"].mean()
        out["q_pos"] = quali.set_index("driver")["position"]
        out["q_gap_pct"] = (quali.set_index("driver")["gap_to_best_s"]
                            / (quali.set_index("driver")["best_lap_s"] - quali.set_index("driver")["gap_to_best_s"]))

        # Form comes from Race results of *earlier* weekends of the same season only.
        hist = self._races[(self._races["year"] == year) & (self._races["round"] < round_number)]
        team_hist = hist.groupby("team")["position"].agg(["sum", "count"])
        drv_hist = hist.groupby("driver")["position"].agg(["sum", "count"])
        out["team_form"] = [self._shrunk(team_hist, t, TEAM_SHRINK) for t in out["team"]]
        out["driver_form"] = [self._shrunk(drv_hist, d, DRIVER_SHRINK) for d in out.index]
        return out.reset_index()[["driver", "team", "team_color", *FEATURES]]

    @staticmethod
    def _shrunk(table: pd.DataFrame, key, m: float) -> float:
        if key not in table.index:
            return PRIOR_POS
        s, n = table.loc[key, "sum"], table.loc[key, "count"]
        return float((s + PRIOR_POS * m) / (n + m))


def fill_for_model(m: pd.DataFrame) -> pd.DataFrame:
    """Missing rank-like values become 'worse than anyone measured' (a driver with no time set
    is not mid-field); missing gaps become the field's worst gap."""
    x = m[FEATURES].astype(float).copy()
    n = len(m)
    for c in ("prac_rank", "lr_rank", "q_pos"):
        x[c] = x[c].fillna(n + 1 if c != "lr_rank" else x["prac_rank"].fillna(n + 1))
    for c in ("prac_gap_pct", "q_gap_pct"):
        x[c] = x[c].fillna(x[c].max() if x[c].notna().any() else 0.0)
    return x
