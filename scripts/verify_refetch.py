"""Re-fetch a stored round and diff the extracted features against what is on disk.

    .venv/bin/python scripts/verify_refetch.py --year 2026 --round 16

The stored tables were built with FastF1 3.8.3; new sessions arrive through 3.9.0, which changed
what some sessions return (Q1 times for drivers who failed the 107% rule are now included, practice
results carry Time/Position, lap times over 150s are accepted when they match the sector sum).

The frozen model must keep seeing the same kind of input it was fitted on, so this re-extracts a
round that is already stored and reports any column whose values moved. Nothing is written: this
only reads and compares.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from f1cc import data, features, store  # noqa: E402

# Columns the predictors actually read. A difference here can move a prediction; a difference
# anywhere else is cosmetic (see f1cc/predict/base.py for where each is consumed).
MODEL_COLS = ["pace_rank", "gap_pct", "longrun_rank", "longrun_delta_s", "position", "grid",
              "best_lap_s", "gap_to_best_s", "new_soft_sets", "q1_s", "q2_s", "q3_s"]


def _compare(old: pd.DataFrame, new: pd.DataFrame, label: str) -> int:
    """Print per-column differences for one session. Returns the number of columns that moved."""
    keys = ["driver"]
    shared = [c for c in old.columns if c in new.columns and c not in keys]
    o = old.set_index(keys).sort_index()
    n = new.set_index(keys).sort_index()

    only_old, only_new = set(o.index) - set(n.index), set(n.index) - set(o.index)
    if only_old or only_new:
        print(f"  {label}: drivers differ  stored-only={sorted(only_old)} fresh-only={sorted(only_new)}")
    common = sorted(set(o.index) & set(n.index))
    o, n = o.loc[common], n.loc[common]

    moved = 0
    for col in shared:
        a, b = o[col], n[col]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            same = np.isclose(a.astype(float), b.astype(float), rtol=1e-6, atol=1e-6, equal_nan=True)
        else:
            same = (a.astype(str) == b.astype(str)) | (a.isna() & b.isna())
        if same.all():
            continue
        moved += 1
        where = [str(d) for d, ok in zip(common, same) if not ok]
        flag = "MODEL" if col in MODEL_COLS else "     "
        print(f"  {flag} {label:12} {col:20} {len(where):2} driver(s): {', '.join(where[:6])}")
        for d in where[:3]:
            print(f"            {d}: stored={a.loc[d]!r} -> fresh={b.loc[d]!r}")
    return moved


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--force-renew", action="store_true",
                    help="bypass the HTTP cache, so the comparison is against what the server "
                         "returns now rather than the response 3.8.3 already stored")
    args = ap.parse_args()

    if args.force_renew:
        import fastf1
        data._setup()
        fastf1.Cache.configure(cache_dir=str(data.CACHE_DIR), force_renew=True)

    stored = store.read("features", [args.year])
    stored = stored[stored["round"] == args.round]
    if stored.empty:
        print(f"nothing stored for {args.year} R{args.round:02d}")
        return 1

    sched = data.get_schedule(args.year)
    row = sched[sched.RoundNumber == args.round].iloc[0]
    print(f"{args.year} R{args.round:02d} {row.EventName}\n")

    total = 0
    for idx, sname in enumerate(data.weekend_sessions(row)):
        old = stored[stored["session"] == sname]
        if old.empty:
            continue
        try:
            fresh, _, _ = features.extract(data.load_session(args.year, args.round, sname), args.year, args.round, idx)
        except Exception as e:
            print(f"  {sname}: FAILED {type(e).__name__}: {str(e)[:120]}")
            total += 1
            continue
        total += _compare(old, fresh, sname)

    print()
    if total:
        print(f"{total} column(s) moved. Anything marked MODEL feeds a predictor: check whether the\n"
              f"frozen model's inputs still match what it was fitted on before storing new rounds.")
    else:
        print("identical: 3.9.0 returns the same values for this round as the stored 3.8.3 extract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
