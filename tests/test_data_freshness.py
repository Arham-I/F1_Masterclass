"""Regression guard for a real bug: backfill.py's resumability treats an (year, round, session)
already on disk as permanently done, even after features.py changes. Three fixes made this
session (hex casing, colour repair, the 107% rule) silently never applied to sessions from the
first backfill run - I only caught it by manually re-extracting one session and diffing.

This makes that diff automatic: re-extract a small, deterministic sample straight from the
(already-warm, local-only) FastF1 cache and compare against what's stored in data/. A mismatch
here means the derived files are stale relative to the current f1cc/features.py and need a
`rm data/*.parquet && python scripts/backfill.py --years ...` rebuild (cheap: it reads the
local cache, no network, no rate limit - see the session log, ~6.5 min for all 460 sessions).

Deliberately slow-ish (real session loads, even from cache) and skipped if the cache is cold,
so it never blocks a fresh checkout - it is a local dev freshness check, not a CI gate.
"""
import warnings
from pathlib import Path

import pandas as pd
import pytest

from f1cc import data, features, store
from tests.test_guard import _fastf1_cache_available

warnings.filterwarnings("ignore", category=FutureWarning)

pytestmark = pytest.mark.skipif(
    not (_fastf1_cache_available() and store.available_years("features")),
    reason="needs both a warm FastF1 cache and existing data/*.parquet to compare against",
)

# One weekend per year: enough variety (a Race plus at least one practice/quali session per
# year) without re-loading the whole dataset on every test run.
SAMPLE_ROUNDS = {2022: 1, 2023: 1, 2024: 1, 2025: 1, 2026: 1}


@pytest.mark.parametrize("year,round_number", sorted(SAMPLE_ROUNDS.items()))
def test_stored_data_matches_a_fresh_extraction(year, round_number):
    sched = data.get_schedule(year)
    row = sched[sched.RoundNumber == round_number].iloc[0]

    fresh = {t: [] for t in store.TABLES}
    for idx, sname in enumerate(data.weekend_sessions(row)):
        session = data.load_session(year, round_number, sname)
        f, l, s = features.extract(session, year, round_number, idx)
        for name, df in zip(store.TABLES, (f, l, s)):
            fresh[name].append(df)

    for table in store.TABLES:
        fresh_df = pd.concat(fresh[table], ignore_index=True)
        stored_df = store.read(table, [year])
        stored_df = stored_df[stored_df["round"] == round_number].reset_index(drop=True)

        key = [c for c in ("session", "driver", "lap", "stint") if c in fresh_df.columns]
        fresh_df = fresh_df.sort_values(key).reset_index(drop=True)
        stored_df = stored_df[fresh_df.columns].sort_values(key).reset_index(drop=True)

        try:
            pd.testing.assert_frame_equal(fresh_df, stored_df, check_exact=False, rtol=1e-6)
        except AssertionError as e:
            raise AssertionError(
                f"data/{table}_{year}.parquet round {round_number} is stale relative to "
                f"f1cc/features.py - rebuild with: rm data/{table}_{year}.parquet && "
                f"python scripts/backfill.py --years {year}\n\n{e}"
            ) from e
