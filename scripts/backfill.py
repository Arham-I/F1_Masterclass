"""Pull sessions from FastF1 and write the derived parquet tables to data/.

Resumable: a (year, round, session) already present in the year's features file is skipped,
so re-running after an interruption (or after a new race weekend) only fetches what is new.

    python scripts/backfill.py --years 2026
    python scripts/backfill.py --years 2025 2024 2023 2022
    python scripts/backfill.py --years 2026 --rounds 14
"""
from __future__ import annotations

import argparse
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd  # noqa: E402

from f1cc import data, features, store  # noqa: E402


RATE_LIMIT_WAIT_S = 300   # FastF1 allows ~500 API calls/hour; cached responses don't count
RATE_LIMIT_MAX_WAITS = 30  # give up on a session after ~2.5h of waiting


def _load_and_extract(year: int, rnd: int, sname: str, idx: int):
    """Load + extract one session, waiting out FastF1's hourly rate limit instead of failing.

    Failing fast here is the trap: after the limit trips, every remaining session errors in
    milliseconds and the whole backfill "finishes" having fetched nothing.
    """
    for attempt in range(RATE_LIMIT_MAX_WAITS + 1):
        try:
            session = data.load_session(year, rnd, sname)
            return features.extract(session, year, rnd, idx)
        except Exception as e:
            if type(e).__name__ != "RateLimitExceededError" or attempt == RATE_LIMIT_MAX_WAITS:
                raise
            print(f"  ...rate limited at {year} R{rnd:02d} {sname}; waiting {RATE_LIMIT_WAIT_S}s "
                  f"(wait {attempt + 1}/{RATE_LIMIT_MAX_WAITS})", flush=True)
            time.sleep(RATE_LIMIT_WAIT_S)


def backfill_year(year: int, rounds: list[int] | None) -> list[tuple]:
    sched = data.get_schedule(year)
    wanted = set(data.completed_rounds(year))
    if rounds:
        wanted &= set(rounds)

    existing = {t: (store.read(t, [year]) if store.path(t, year).exists() else pd.DataFrame())
                for t in store.TABLES}
    done = set()
    if len(existing["features"]):
        done = set(zip(existing["features"]["round"], existing["features"]["session"]))

    failures: list[tuple] = []
    for rnd in sorted(wanted):
        row = sched[sched.RoundNumber == rnd].iloc[0]
        new = {t: [] for t in store.TABLES}
        for idx, sname in enumerate(data.weekend_sessions(row)):
            if (rnd, sname) in done:
                continue
            t0 = time.time()
            try:
                f, l, s = _load_and_extract(year, rnd, sname, idx)
            except Exception as e:  # keep going: one bad session must not sink the backfill
                failures.append((year, rnd, sname, type(e).__name__, str(e)[:120]))
                print(f"  FAIL {year} R{rnd:02d} {sname}: {type(e).__name__}: {str(e)[:100]}", flush=True)
                continue
            for name, df in zip(store.TABLES, (f, l, s)):
                new[name].append(df)
            print(f"  ok   {year} R{rnd:02d} {row.EventName:26} {sname:11} ({time.time()-t0:4.1f}s)", flush=True)

        if any(new[t] for t in store.TABLES):
            for t in store.TABLES:
                existing[t] = pd.concat([existing[t], *new[t]], ignore_index=True)
                store.write(t, year, existing[t])  # checkpoint after every weekend

    # Whole-year repair pass (runs even when nothing new was fetched, so old files get fixed too).
    if len(existing["features"]):
        existing["features"], existing["laps"] = features.repair_teams(existing["features"], existing["laps"])
        for t in ("features", "laps"):
            store.write(t, year, existing[t])
    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", type=int, nargs="+", required=True)
    ap.add_argument("--rounds", type=int, nargs="*", help="restrict to these round numbers")
    args = ap.parse_args()

    t0 = time.time()
    all_failures: list[tuple] = []
    for year in args.years:
        print(f"== {year}", flush=True)
        all_failures += backfill_year(year, args.rounds)
        print(f"[{time.time()-t0:5.0f}s] finished {year}", flush=True)

    if all_failures:
        print(f"\n{len(all_failures)} FAILED sessions:")
        for f in all_failures:
            print("  ", f)
        return 1
    print("\nall sessions ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
