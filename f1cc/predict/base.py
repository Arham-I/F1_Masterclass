"""Shared plumbing for predictors: leak-safe feature matrices and win/podium probabilities.

A predictor answers one question: given a weekend and a cutoff, how will the Race finish?
Everything it may know comes from exactly two places:

* the weekend's own sessions that ``apply_cutoff`` reveals (never the Race), and
* Race results of weekends that finished *strictly before* this one (form, reliability,
  training data and the predictor's own past errors).

``FeatureBuilder.matrix`` is the only door to a weekend's sessions and ``FeatureBuilder.result``
the only door to Race results; both enforce these rules, so predictors built on them cannot
leak, and the backtest is fair by construction.

Probabilities come from :func:`simulate`: a retirement draw per driver (team reliability so far
this season) plus finishing-order noise whose size grows down the order (fitted to the
predictor's own out-of-sample errors on earlier weekends).
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd

from ..replay import Cutoff, Weekend, apply_cutoff

PRIOR_POS = 10.5           # mean finishing position of a 20-car field: what "no history" means
TEAM_SHRINK = 4.0          # pseudo-observations of PRIOR_POS mixed into a team's form (2 cars/race)
DRIVER_SHRINK = 2.0
DNF_SHRINK = 20.0          # pseudo-starts of the long-run retirement rate mixed into a team's season rate
ERROR_WINDOW = 40          # earlier weekends whose prediction errors size the noise
MIN_SIGMA = 0.75           # places; even a dominant pole sitter is never a certainty
FALLBACK_SIGMA = 3.5       # places, when there are no earlier errors to learn from
SPRINT_QUALI = ("Sprint Qualifying", "Sprint Shootout")
FINISHED = ("Finished", "Lapped")
FEATURES = ["prac_rank", "prac_gap_pct", "lr_rank", "sprint_rank", "sprint_pos", "q_pos", "q_gap_pct",
            "team_form", "driver_form"]
OUTPUT = ["driver", "team", "team_color", "score", "expected_pos", "sigma", "p_dnf", "p_win", "p_podium",
          "p_pos"]         # p_pos: list of chances of finishing P1..Pn


class Predictor(Protocol):
    name: str

    def predict(self, cutoff: Cutoff) -> pd.DataFrame:
        """Columns: see ``OUTPUT``. ``sigma`` is the noise (in places) for that driver."""


def finished(status: pd.Series) -> pd.Series:
    return status.isin(FINISHED) | status.str.startswith("+")


def simulate(center: np.ndarray, sigma, p_dnf: np.ndarray | None = None, n: int = 20000,
             seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Win and podium probabilities (see :func:`position_distribution`)."""
    dist = position_distribution(center, sigma, p_dnf, n, seed)
    return dist[:, 0], dist[:, :3].sum(axis=1)


def position_distribution(center: np.ndarray, sigma, p_dnf: np.ndarray | None = None,
                          n: int = 20000, seed: int = 0) -> np.ndarray:
    """``[driver, position]`` probabilities. Each run: every driver retires with probability
    ``p_dnf`` (and drops to the back); the rest finish in order of ``center`` plus Gaussian noise
    of size ``sigma`` (a scalar or one value per driver, in places)."""
    rng = np.random.default_rng(seed)
    center = np.asarray(center, dtype=float)
    sigma = np.broadcast_to(np.asarray(sigma, dtype=float), center.shape)
    sim = center[None, :] + sigma[None, :] * rng.standard_normal((n, len(center)))
    if p_dnf is not None:
        sim = sim + 1e6 * (rng.random((n, len(center))) < np.asarray(p_dnf)[None, :])
    rank = sim.argsort(axis=1).argsort(axis=1)
    return np.stack([(rank == p).mean(axis=0) for p in range(len(center))], axis=1)


def rps(dist: np.ndarray, actual_place: np.ndarray) -> float:
    """Ranked probability score over the whole grid (0 = perfect, lower is better): for every
    driver, how far the predicted cumulative chance of finishing P1..Pn is from what happened.
    Unlike win log-loss it rewards 'about P8' for a P9 finish and punishes it for a P18."""
    n = dist.shape[1]
    idx = np.clip(np.asarray(actual_place, dtype=int), 1, n) - 1
    observed = (np.arange(n)[None, :] >= idx[:, None]).astype(float)
    return float((((dist.cumsum(axis=1) - observed) ** 2).sum(axis=1) / (n - 1)).mean())


def _is_before(df: pd.DataFrame, year: int, round_number: int) -> pd.Series:
    return (df["year"] < year) | ((df["year"] == year) & (df["round"] < round_number))


class FeatureBuilder:
    """Turns the features table into one row per driver for (year, round, k sessions revealed)."""

    def __init__(self, features: pd.DataFrame):
        self.features = features
        races = features[features["session"] == "Race"].dropna(subset=["position"])
        self._races = races[["year", "round", "driver", "team", "position"]].assign(
            dnf=~finished(races["status"].fillna("")))
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

    def result(self, year: int, round_number: int) -> pd.DataFrame:
        """Race result (driver, position, dnf). Callers must only ask about weekends that are
        already over relative to what they predict - i.e. from ``weekends_before``."""
        r = self._races[(self._races["year"] == year) & (self._races["round"] == round_number)]
        return r[["driver", "position", "dnf"]].reset_index(drop=True)

    def matrix(self, year: int, round_number: int, k: int, with_target: bool = False) -> pd.DataFrame:
        key = (year, round_number, k)
        if key not in self._cache:
            self._cache[key] = self._build(year, round_number, k)
        m = self._cache[key]
        if not with_target:
            return m
        actual = self.result(year, round_number).set_index("driver")["position"]
        return m.assign(actual=m["driver"].map(actual))

    def dnf_prob(self, year: int, round_number: int, teams) -> np.ndarray:
        """Retirement chance per team: its rate so far this season, shrunk toward the retirement
        rate of every earlier race (team names and cars change between seasons, so earlier
        seasons only set the prior)."""
        before = self._races[_is_before(self._races, year, round_number)]
        if before.empty:
            return np.full(len(teams), 0.1)
        overall = before["dnf"].mean()
        season = before[before["year"] == year].groupby("team")["dnf"].agg(["sum", "count"])
        return np.array([
            (season.loc[t, "sum"] + DNF_SHRINK * overall) / (season.loc[t, "count"] + DNF_SHRINK)
            if t in season.index else overall for t in teams])

    def _build(self, year: int, round_number: int, k: int) -> pd.DataFrame:
        cutoff = Cutoff(self.weekend(year, round_number), k)
        vis = apply_cutoff(self.features, cutoff)          # the ONLY rows of this weekend we touch
        if vis.empty:
            return pd.DataFrame(columns=["driver", "team", "team_color", "sq_rank", *FEATURES])
        # FP1 stand-ins (e.g. rookies in their mandatory FP1 outing) do not race. A driver seen
        # only in the first session is a stand-in when his team has already fielded two *other*
        # drivers since - not merely because he missed a later session (crash repairs, a wet FP2).
        first = vis["session_idx"].min()
        later = vis[vis["session_idx"] > first]
        if not later.empty:
            fielded = later.groupby("team")["driver"].nunique()
            first_only = vis[~vis["driver"].isin(later["driver"])]
            stand_ins = first_only.loc[first_only["team"].map(fielded).fillna(0) >= 2, "driver"]
            vis = vis[~vis["driver"].isin(stand_ins)]

        practice = vis[vis["session"].str.startswith("Practice")].copy()
        practice["gap_pct"] = practice["gap_to_best_s"] / (practice["best_lap_s"] - practice["gap_to_best_s"])
        quali = vis[vis["session"] == "Qualifying"].set_index("driver")
        # Sprint qualifying has no classified position in the feed, so its order is best-lap rank.
        sprint_quali = vis[vis["session"].isin(SPRINT_QUALI)].set_index("driver")
        sprint = vis[vis["session"] == "Sprint"].set_index("driver")

        last = vis.sort_values("session_idx").groupby("driver").last()
        out = pd.DataFrame({"driver": last.index, "team": last["team"].to_numpy(),
                            "team_color": last["team_color"].to_numpy()}).set_index("driver")
        out["prac_rank"] = practice.groupby("driver")["pace_rank"].mean()
        out["prac_gap_pct"] = practice.groupby("driver")["gap_pct"].mean()
        out["lr_rank"] = practice.groupby("driver")["longrun_rank"].mean()
        out["sq_rank"] = sprint_quali["pace_rank"]
        out["sprint_pos"] = sprint["position"]
        # Sprint-qualifying order alone: on 2024-25 sprint weekends it predicted the race better
        # (Spearman 0.589) than practice pace (0.398) or its average with the Sprint result (0.582).
        out["sprint_rank"] = out["sq_rank"]
        out["q_pos"] = quali["position"]
        out["q_gap_pct"] = quali["gap_to_best_s"] / (quali["best_lap_s"] - quali["gap_to_best_s"])

        # Form comes from Race results of *earlier* weekends of the same season only.
        hist = self._races[(self._races["year"] == year) & (self._races["round"] < round_number)]
        team_hist = hist.groupby("team")["position"].agg(["sum", "count"])
        drv_hist = hist.groupby("driver")["position"].agg(["sum", "count"])
        out["team_form"] = [self._shrunk(team_hist, t, TEAM_SHRINK) for t in out["team"]]
        out["driver_form"] = [self._shrunk(drv_hist, d, DRIVER_SHRINK) for d in out.index]
        return out.reset_index()[["driver", "team", "team_color", "sq_rank", *FEATURES]]

    @staticmethod
    def _shrunk(table: pd.DataFrame, key, m: float) -> float:
        if key not in table.index:
            return PRIOR_POS
        s, n = table.loc[key, "sum"], table.loc[key, "count"]
        return float((s + PRIOR_POS * m) / (n + m))


def fill_for_model(m: pd.DataFrame) -> pd.DataFrame:
    """Missing rank-like values become 'worse than anyone measured' (a driver with no time set
    is not mid-field); missing gaps become the field's worst gap. Without a sprint session the
    sprint order falls back to practice pace, so the column means "best pre-qualifying order"."""
    x = m[FEATURES].astype(float).copy()
    n = len(m)
    x["prac_rank"] = x["prac_rank"].fillna(n + 1)
    x["lr_rank"] = x["lr_rank"].fillna(x["prac_rank"])
    x["sprint_rank"] = x["sprint_rank"].fillna(x["prac_rank"])
    x["sprint_pos"] = x["sprint_pos"].fillna(x["sprint_rank"])
    x["q_pos"] = x["q_pos"].fillna(n + 1)
    for c in ("prac_gap_pct", "q_gap_pct"):
        x[c] = x[c].fillna(x[c].max() if x[c].notna().any() else 0.0)
    return x


class SimulatedPredictor:
    """Base for predictors: subclasses only provide ``_score`` (lower = finishes ahead) for a
    feature matrix. Turning scores into probabilities is shared and calibrated on the
    predictor's *own* past mistakes: its point predictions for the previous ``ERROR_WINDOW``
    weekends (each made without that weekend's result) against what actually happened."""

    name = "?"

    def __init__(self, features: pd.DataFrame | None, builder: FeatureBuilder | None = None):
        self.builder = builder or FeatureBuilder(features)
        self._points: dict[tuple[int, int, int], np.ndarray] = {}
        self._errors: dict[tuple[int, int, int], tuple[float, float]] = {}

    def _score(self, m: pd.DataFrame, year: int, round_number: int, k: int) -> np.ndarray:
        raise NotImplementedError

    def point(self, year: int, round_number: int, k: int) -> np.ndarray:
        key = (year, round_number, k)
        if key not in self._points:
            m = self.builder.matrix(year, round_number, k)
            self._points[key] = self._score(m, year, round_number, k) if len(m) else np.array([])
        return self._points[key]

    def error_model(self, year: int, round_number: int, k: int) -> tuple[float, float]:
        """(a, b) with expected |error| = a + b * predicted place, among cars that finished,
        from this predictor's out-of-sample predictions on earlier weekends at the same stage."""
        key = (year, round_number, k)
        if key in self._errors:
            return self._errors[key]
        place, err = [], []
        for (y, r) in self.builder.weekends_before(year, round_number)[-ERROR_WINDOW:]:
            m = self.builder.matrix(y, r, k)
            if len(m) < 10:
                continue
            res = m[["driver"]].assign(score=self.point(y, r, k)).merge(self.builder.result(y, r), on="driver")
            res = res[~res["dnf"]]
            place.append(res["score"].rank(method="first").to_numpy())
            err.append(np.abs(res["position"].rank(method="first").to_numpy() - place[-1]))
        if sum(map(len, place)) < 100:
            fit = (FALLBACK_SIGMA / np.sqrt(np.pi / 2), 0.0)
        else:
            b, a = np.polyfit(np.concatenate(place), np.concatenate(err), 1)
            fit = (float(a), float(b))
        self._errors[key] = fit
        return fit

    def _center(self, m: pd.DataFrame, place: np.ndarray, year: int, round_number: int, k: int) -> np.ndarray:
        """Where each driver sits in the simulation, in places. Default: the predicted place."""
        return place

    def noise(self, year: int, round_number: int, k: int):
        """(matrix, score, place, sigma, p_dnf) for a weekend - everything the simulation needs
        except the centre."""
        m = self.builder.matrix(year, round_number, k)
        score = self.point(year, round_number, k)
        place = pd.Series(score).rank(method="first").to_numpy()
        a, b = self.error_model(year, round_number, k)
        sigma = np.maximum(MIN_SIGMA, np.sqrt(np.pi / 2) * (a + b * place))   # |N(0,s)| has mean s*sqrt(2/pi)
        return m, score, place, sigma, self.builder.dnf_prob(year, round_number, m["team"])

    def predict(self, cutoff: Cutoff) -> pd.DataFrame:
        w, k = cutoff.weekend, cutoff.revealed
        if self.builder.matrix(w.year, w.round, k).empty:
            return pd.DataFrame(columns=OUTPUT)
        m, score, place, sigma, p_dnf = self.noise(w.year, w.round, k)
        dist = position_distribution(self._center(m, place, w.year, w.round, k), sigma, p_dnf)
        out = m[["driver", "team", "team_color"]].copy()
        out["score"], out["expected_pos"], out["sigma"], out["p_dnf"] = score, place.astype(int), sigma, p_dnf
        out["p_win"], out["p_podium"] = dist[:, 0], dist[:, :3].sum(axis=1)
        out["p_pos"] = list(dist)
        return out.sort_values("expected_pos").reset_index(drop=True)[OUTPUT]
