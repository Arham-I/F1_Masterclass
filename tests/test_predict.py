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
from f1cc.predict.base import FEATURES, OUTPUT, position_distribution, rps
from f1cc.predict.baseline import TIME_WEIGHT
from f1cc.replay import Cutoff

pytestmark = pytest.mark.skipif(not store.available_years("features"), reason="needs data/*.parquet")

YEAR, ROUND = 2026, 14
SPRINT_ROUND = 12                                          # FP1, Sprint Qualifying, Sprint, Qualifying
NUMERIC = ["position", "best_lap_s", "gap_to_best_s", "pace_rank", "longrun_rank", "q1_s", "q2_s", "q3_s",
           "new_soft_sets"]


@pytest.fixture(scope="module")
def features():
    return store.read("features")


def _scramble(df: pd.DataFrame, mask: pd.Series, seed: int = 1) -> pd.DataFrame:
    """Replace numeric values and finishing status in the masked rows with random junk."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    for c in NUMERIC:
        out[c] = out[c].astype(float)
        out.loc[mask, c] = rng.uniform(1, 20, mask.sum())
    out.loc[mask, "status"] = rng.choice(["Finished", "Retired"], mask.sum())
    return out


def _run(predictor_cls, features, k, rnd=ROUND, **kw):
    b = FeatureBuilder(features)
    return predictor_cls(features, b, **kw).predict(Cutoff(b.weekend(YEAR, rnd), k))


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
@pytest.mark.parametrize("k", [1, 2, 3])
def test_sprint_weekend_prediction_ignores_later_sessions_and_the_race(features, predictor_cls, k):
    b = FeatureBuilder(features)
    later = b.weekend(YEAR, SPRINT_ROUND).replayable[k:] + ("Race",)
    mask = ((features["year"] == YEAR) & (features["round"] == SPRINT_ROUND) & features["session"].isin(later))
    _same(_run(predictor_cls, features, k, SPRINT_ROUND),
          _run(predictor_cls, _scramble(features, mask), k, SPRINT_ROUND))


def test_sprint_qualifying_moves_the_baseline_before_qualifying(features):
    b = FeatureBuilder(features)
    p = BaselinePredictor(features, b)
    assert b.weekend(YEAR, SPRINT_ROUND).replayable[1] == "Sprint Qualifying"
    assert b.matrix(YEAR, SPRINT_ROUND, 1)["sprint_rank"].isna().all()
    assert b.matrix(YEAR, SPRINT_ROUND, 2)["sprint_rank"].notna().any()
    assert not np.array_equal(p.point(YEAR, SPRINT_ROUND, 1).argsort(), p.point(YEAR, SPRINT_ROUND, 2).argsort())


def test_after_qualifying_extras_only_exist_once_qualifying_is_visible(features):
    b = FeatureBuilder(features)
    for k in (1, 2, 3):
        m = b.matrix(YEAR, ROUND, k)
        assert m["tm_delta"].isna().all()
        pd.testing.assert_series_equal(m["prac_rank_w"], m["prac_rank"], check_names=False)
    m = b.matrix(YEAR, ROUND, 4)
    assert m["tm_delta"].notna().sum() >= 18                        # most drivers have a timed teammate
    assert (m["tm_delta"].groupby(m["team"]).sum().abs() < 1e-9).all()   # teammates mirror each other
    for same_year in (False, True):
        r = RidgePredictor(features, b, same_year_only=same_year)
        assert r.feature_names(b.matrix(YEAR, ROUND, 3)) == list(FEATURES)
        assert r.feature_names(m) != list(FEATURES)


def test_new_soft_sets_count_only_visible_sessions(features):
    b = FeatureBuilder(features)
    later = ((features["year"] == YEAR) & (features["round"] == ROUND)
             & features["session"].isin(["Practice 3", "Qualifying", "Race"]))
    before = b.matrix(YEAR, ROUND, 2)["new_soft"]
    after = FeatureBuilder(_scramble(features, later)).matrix(YEAR, ROUND, 2)["new_soft"]
    pd.testing.assert_series_equal(before, after)


def test_fp1_stand_ins_leave_once_a_later_session_is_visible(features):
    b = FeatureBuilder(features)
    # 2026 R7: seven rookies drove FP1 in place of race drivers (e.g. ARO for a race seat).
    assert "ARO" in set(b.matrix(YEAR, 7, 1)["driver"])
    assert "ARO" not in set(b.matrix(YEAR, 7, 2)["driver"])
    assert {"HAM", "NOR", "ANT"} <= set(b.matrix(YEAR, 7, 2)["driver"])   # the race drivers they stood in for
    # ...but a race driver who merely missed FP2 (2026 R5: LAW, ALB) is not mistaken for one.
    assert {"LAW", "ALB"} <= set(b.matrix(YEAR, 5, 2)["driver"])


def test_retirement_chance_uses_this_seasons_earlier_races_only(features):
    b = FeatureBuilder(features)
    teams = b.matrix(YEAR, ROUND, 4)["team"]
    p = b.dnf_prob(YEAR, ROUND, teams)
    assert ((p > 0) & (p < 1)).all()
    later = (features["year"] == YEAR) & (features["round"] >= ROUND)
    np.testing.assert_array_equal(p, FeatureBuilder(_scramble(features, later)).dnf_prob(YEAR, ROUND, teams))


def test_noise_is_fitted_on_earlier_weekends_only(features):
    later = (features["year"] == YEAR) & (features["round"] >= ROUND)
    fit = lambda f: RidgePredictor(f, FeatureBuilder(f)).error_model(YEAR, ROUND, 4)
    assert fit(features) == fit(_scramble(features, later))


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
    p_dnf = np.zeros(20); p_dnf[0] = 1.0
    out, out_pod = simulate(score, sigma=np.linspace(1, 4, 20), p_dnf=p_dnf)
    assert out[0] == 0 and out_pod[0] == 0                 # a certain retirement never wins
    assert out.sum() == pytest.approx(1.0) and out_pod.sum() == pytest.approx(3.0)


def test_position_distribution_is_a_proper_distribution():
    dist = position_distribution(np.arange(1, 21, dtype=float), np.linspace(1, 4, 20), np.full(20, 0.1))
    np.testing.assert_allclose(dist.sum(axis=1), 1)        # every driver finishes somewhere
    np.testing.assert_allclose(dist.sum(axis=0), 1)        # every position is taken by someone
    win, pod = simulate(np.arange(1, 21, dtype=float), np.linspace(1, 4, 20), np.full(20, 0.1))
    np.testing.assert_allclose(win, dist[:, 0])
    np.testing.assert_allclose(pod, dist[:, :3].sum(axis=1))


def test_rps_rewards_near_misses_over_far_misses():
    sure = np.eye(5)                                       # driver i certain to finish P(i+1)
    assert rps(sure, np.arange(1, 6)) == 0
    near, far = np.arange(1, 6), np.array([5, 2, 3, 4, 1])
    assert 0 < rps(sure, np.array([2, 1, 3, 4, 5])) < rps(sure, far)
    assert rps(sure, near) < rps(sure, far)


def test_time_scale_only_after_qualifying_and_never_reorders(features):
    b = FeatureBuilder(features)
    p = BaselinePredictor(features, b)
    for k in (1, 2, 3):                                    # no qualifying yet: simulate on grid places
        m, _, place, _, _ = p.noise(YEAR, ROUND, k)
        np.testing.assert_array_equal(p._center(m, place, YEAR, ROUND, k), place)
    m, _, place, _, _ = p.noise(YEAR, ROUND, 4)
    center = p._center(m, place, YEAR, ROUND, 4)
    assert not np.allclose(center, place)                  # gaps are used after qualifying
    assert np.corrcoef(center, place)[0, 1] > 0.95
    plain = BaselinePredictor(features, b)
    plain._center = lambda m, place, *a: place
    live = p.predict(Cutoff(b.weekend(YEAR, ROUND), 4))
    np.testing.assert_array_equal(live["driver"], plain.predict(Cutoff(b.weekend(YEAR, ROUND), 4))["driver"])


def test_close_qualifying_gap_means_closer_race_odds(features):
    """The time scale's whole point: the pole sitter's edge over P2 depends on the gap."""
    b = FeatureBuilder(features)
    p = BaselinePredictor(features, b)
    m, _, place, sigma, p_dnf = p.noise(YEAR, ROUND, 4)
    center = p._center(m, place, YEAR, ROUND, 4)
    gap = p._gaps(m)
    p2 = int(np.flatnonzero(place == 2)[0])
    w = TIME_WEIGHT
    assert center[p2] == pytest.approx((1 - w) * 2 + w * (1 + gap[p2] / p._pct_per_place(YEAR, ROUND, 4)))


def test_prediction_output_shape(features):
    out = _run(BaselinePredictor, features, 4)
    assert list(out.columns) == OUTPUT
    assert (out["sigma"] > 0).all() and out["p_dnf"].between(0, 1).all()
    assert sorted(out["expected_pos"]) == list(range(1, len(out) + 1))


def test_stored_predictions_match_a_live_prediction(features):
    stored = store.read("predictions", [YEAR])
    if stored.empty:
        pytest.skip("run scripts/backtest.py first")
    b = FeatureBuilder(features)
    for stage in (2, 4):                                   # 4 exercises the time scale
        live = BaselinePredictor(features, b).predict(Cutoff(b.weekend(YEAR, ROUND), stage))
        keep = stored[(stored["round"] == ROUND) & (stored["stage"] == stage)
                      & (stored["predictor"] == BaselinePredictor.name)]
        cols = ["driver", "score", "sigma", "p_dnf", "p_win", "p_podium"]
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
