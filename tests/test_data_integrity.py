"""Invariant checks against the REAL backfilled dataset (all cached years, no network).

Every other test file uses hand-built synthetic data, which only tests the rules I already
thought of. Every real bug found while building this project (the 107% rule deleting
practice long runs, a whole session missing team data, colour repair missing rows where only
the colour was blank, stale sessions surviving a code fix) was found by manually inspecting
data/*.parquet, not by a test. This file is that inspection, made permanent and automatic.

All assertions here were verified true against the full 2022-2026 dataset before being
written (see the session log) - this is a regression guard, not a guess about the data.

Skipped entirely if data/ hasn't been populated yet (e.g. a fresh checkout before backfill).
"""
import re

import pandas as pd
import pytest

from f1cc import store

YEARS = store.available_years("features")
pytestmark = pytest.mark.skipif(not YEARS, reason="no data/*.parquet - run scripts/backfill.py first")

HEX_RE = re.compile(r"^#[0-9A-F]{6}$")
DRY = {"SOFT", "MEDIUM", "HARD"}
KNOWN_SESSIONS = {"Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race",
                 "Sprint", "Sprint Qualifying", "Sprint Shootout"}


@pytest.fixture(scope="module")
def tables():
    return store.read("features"), store.read("laps"), store.read("stints")


def test_gap_to_best_is_never_negative_and_zero_for_the_session_leader(tables):
    f, _, _ = tables
    assert (f["gap_to_best_s"].dropna() >= 0).all()
    mins = f.groupby(["year", "round", "session"])["gap_to_best_s"].min().dropna()
    assert (mins == 0).all()


def test_pace_rank_is_a_positive_integer_when_present(tables):
    f, _, _ = tables
    r = f["pace_rank"].dropna()
    assert (r >= 1).all() and ((r % 1) == 0).all()


def test_team_color_is_always_a_well_formed_hex_code(tables):
    f, _, _ = tables
    assert f["team_color"].apply(lambda x: bool(HEX_RE.fullmatch(str(x)))).all()


def test_team_is_never_blank(tables):
    f, _, _ = tables
    assert (f["team"].fillna("").str.strip() != "").all()


def test_longrun_delta_is_only_ever_set_on_dry_compounds(tables):
    """Guards the wet-weather design decision: no run should mix in inter/wet laps."""
    _, laps, _ = tables
    dry_only = laps.loc[laps["longrun_delta_s"].notna(), "compound"]
    assert dry_only.isin(DRY).all()


def test_stint_lap_ranges_are_well_formed_and_contiguous(tables):
    _, _, stints = tables
    assert (stints["lap_start"] <= stints["lap_end"]).all()
    assert (stints["n_laps"] == stints["lap_end"] - stints["lap_start"] + 1).all()


def test_no_duplicate_driver_rows_within_a_session(tables):
    f, laps, _ = tables
    assert not f.duplicated(subset=["year", "round", "session", "driver"]).any()
    assert not laps.duplicated(subset=["year", "round", "session", "driver", "lap"]).any()


def test_every_session_name_is_a_known_one(tables):
    """Catches a garbage/typo'd session label slipping in from a schedule quirk."""
    f, _, _ = tables
    assert set(f["session"].unique()) <= KNOWN_SESSIONS


def test_laps_and_stints_never_reference_a_session_missing_from_features(tables):
    f, laps, stints = tables
    known = set(zip(f["year"], f["round"], f["session"]))
    assert set(zip(laps["year"], laps["round"], laps["session"])) <= known
    assert set(zip(stints["year"], stints["round"], stints["session"])) <= known


def test_grid_position_present_whenever_a_classified_result_exists(tables):
    """Race/Sprint sessions should carry a grid position for every classified finisher -
    the baseline predictor (Day 2) depends on this being reliably populated."""
    f, _, _ = tables
    race_like = f[f["session"].isin(["Race", "Sprint"])]
    classified = race_like[race_like["position"].notna()]
    assert classified["grid"].notna().mean() > 0.95  # allow a handful of DSQ/edge cases
