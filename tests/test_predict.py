"""Leakage and sanity tests for the predictors, on the real derived data.

The important property: a prediction made at a cutoff is a function of only (a) sessions
revealed by that cutoff and (b) Race results of strictly earlier weekends. Each test scrambles
everything a predictor is NOT allowed to see and asserts the output does not move.
"""
import numpy as np
import pandas as pd
import pytest

from f1cc import backtest_summary as bts
from f1cc import store
from f1cc.predict import BaselinePredictor, FeatureBuilder, RidgePredictor, simulate
from f1cc.predict.base import FEATURES
from f1cc.replay import Cutoff

pytestmark = pytest.mark.skipif(not store.available_years("features"), reason="needs data/*.parquet")

YEAR, ROUND = 2026, 14
NUMERIC = ["position", "best_lap_s", "gap_to_best_s", "pace_rank", "longrun_rank", "q1_s", "q2_s", "q3_s"]


@pytest.fixture(scope="module")
def features():
    return store.read("features")


def _scramble(df: pd.DataFrame, mask: pd.Series, seed: int = 1) -> pd.DataFrame:
    """Replace numeric values in the masked rows with random junk."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    for c in NUMERIC:
        out.loc[mask, c] = rng.uniform(1, 20, mask.sum())
    return out


def _run(predictor_cls, features, k, **kw):
    b = FeatureBuilder(features)
    return predictor_cls(features, b, **kw).predict(Cutoff(b.weekend(YEAR, ROUND), k))


def _same(a: pd.DataFrame, b: pd.DataFrame):
    pd.testing.assert_frame_equal(a.reset_index(drop=True), b.reset_index(drop=True))


@pytest.mark.parametrize("predictor_cls", [BaselinePredictor, RidgePredictor])
@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_prediction_ignores_the_race_it_is_predicting(features, predictor_cls, k):
    is_target_race = (features["year"] == YEAR) & (features["round"] == ROUND) & (features["session"] == "Race")
    _same(_run(predictor_cls, features, k), _run(predictor_cls, _scramble(features, is_target_race), k))


@pytest.mark.parametrize("predictor_cls", [BaselinePredictor, RidgePredictor])
@pytest.mark.parametrize("k", [1, 2, 3])
def test_prediction_ignores_sessions_after_the_cutoff(features, predictor_cls, k):
    b = FeatureBuilder(features)
    later = b.weekend(YEAR, ROUND).replayable[k:]
    mask = ((features["year"] == YEAR) & (features["round"] == ROUND) & features["session"].isin(later))
    assert mask.any()
    _same(_run(predictor_cls, features, k), _run(predictor_cls, _scramble(features, mask), k))


@pytest.mark.parametrize("predictor_cls", [BaselinePredictor, RidgePredictor])
def test_prediction_ignores_later_weekends(features, predictor_cls):
    rnd = 10                                               # mid-season, so rounds 11-14 exist
    mask = (features["year"] == YEAR) & (features["round"] > rnd)
    assert mask.any()

    def run(f):
        b = FeatureBuilder(f)
        return predictor_cls(f, b).predict(Cutoff(b.weekend(YEAR, rnd), 4))
    _same(run(features), run(_scramble(features, mask)))


def test_expanding_window_only_lists_earlier_weekends(features):
    b = FeatureBuilder(features)
    before = b.weekends_before(YEAR, ROUND)
    assert before and all((y, r) < (YEAR, ROUND) for y, r in before)
    assert (YEAR, ROUND) not in before and (YEAR, ROUND + 1) not in before


def test_grid_feature_only_exists_once_qualifying_is_revealed(features):
    b = FeatureBuilder(features)
    for k in (1, 2, 3):
        assert b.matrix(YEAR, ROUND, k)["q_pos"].isna().all()
    assert b.matrix(YEAR, ROUND, 4)["q_pos"].notna().any()


def test_features_matrix_never_contains_the_target(features):
    b = FeatureBuilder(features)
    assert "actual" not in b.matrix(YEAR, ROUND, 4).columns
    assert set(FEATURES) <= set(b.matrix(YEAR, ROUND, 4).columns)


def test_probabilities_are_coherent():
    score = np.arange(1, 21, dtype=float)
    win, pod = simulate(score, sigma=3.0)
    assert win.sum() == pytest.approx(1.0) and pod.sum() == pytest.approx(3.0)
    assert win[0] > win[5] > win[15]                       # better score -> more likely to win
    tight, _ = simulate(score, sigma=0.1)
    assert tight[0] > win[0]                               # less noise -> more certain


def test_stored_predictions_match_a_live_prediction(features):
    stored = store.read("predictions", [YEAR])
    if stored.empty:
        pytest.skip("run scripts/backtest.py first")
    b = FeatureBuilder(features)
    live = BaselinePredictor(features, b).predict(Cutoff(b.weekend(YEAR, ROUND), 2))
    keep = stored[(stored["round"] == ROUND) & (stored["stage"] == 2)
                  & (stored["predictor"] == BaselinePredictor.name)]
    cols = ["driver", "score", "sigma", "p_win", "p_podium"]
    pd.testing.assert_frame_equal(live[cols].reset_index(drop=True), keep[cols].reset_index(drop=True))


def test_backtest_covers_every_race_and_stage():
    bt = store.read("backtest", [YEAR])
    if bt.empty:
        pytest.skip("run scripts/backtest.py first")
    assert set(bt["stage"]) == {1, 2, 3, 4}
    assert bt.groupby(["round", "stage"])["predictor"].nunique().eq(3).all()
    assert bt["spearman"].between(-1, 1).all()


def test_paired_diff_of_a_predictor_with_itself_is_zero():
    bt = pd.DataFrame({"stage": 1, "round": range(6), "predictor": bts.BASELINE, "spearman": np.linspace(0.3, 0.8, 6)})
    d = bts.paired_diff(bt, bts.BASELINE)
    assert d["diff"].iloc[0] == 0 and not d["significant"].iloc[0]
