"""Keep the site current: pull any session that has finished, re-score, re-export.

Meant to be run on a timer (cron) through a race weekend. It is cheap and quiet when there is
nothing to do - it only looks at the local schedule and the stored data, and exits - so running it
every 15 minutes costs nothing and no FastF1 call is made until a session is actually due.

A session becomes due 30 minutes after it ends (the race, 60 - post-race penalties can still move
the order). See ``f1cc.data.session_ready_at``.

    python scripts/auto_update.py                 # pull, re-score, re-export if anything is due
    python scripts/auto_update.py --push          # ...and commit + push, so Vercel redeploys
    python scripts/auto_update.py --dry-run       # say what is due, change nothing
    python scripts/auto_update.py --force         # run the pipeline even if nothing new is due

Exit codes: 0 did something or nothing was due, 1 a step failed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402

from f1cc import data, store  # noqa: E402

YEAR = 2026
ROOT = store.ROOT
LOCK = ROOT / ".auto_update.lock"
LOCK_STALE_S = 3 * 3600        # a run that outlives this was killed; ignore its lock


def due_sessions(year: int, now: pd.Timestamp | None = None) -> list[tuple[int, str]]:
    """(round, session) pairs that have finished but are not stored yet, oldest first."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC").tz_localize(None)
    sched = data.get_schedule(year)
    have = store.read("features", [year]) if store.path("features", year).exists() else pd.DataFrame()
    stored = set(zip(have["round"], have["session"])) if len(have) else set()
    out = []
    for _, row in sched.iterrows():
        rnd = int(row.RoundNumber)
        for name in data.finished_sessions(row, now, include_race=True):
            if (rnd, name) not in stored:
                out.append((rnd, name))
    return out


def run(step: str, args: list[str]) -> None:
    """Run a pipeline step with this interpreter, streaming its output. Raises on failure."""
    print(f"\n--- {step}", flush=True)
    t0 = time.time()
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError(f"{step} failed (exit {r.returncode})")
    print(f"--- {step} ok ({time.time() - t0:.0f}s)", flush=True)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def publish(label: str) -> bool:
    """Commit the regenerated data and push. Returns False if there was nothing to commit."""
    paths = ["data", "web/data", "web/public/data"]
    git("add", *paths)
    if not git("diff", "--cached", "--name-only"):
        print("nothing to commit", flush=True)
        return False
    subprocess.run(["git", "commit", "-m", f"Data: {label}"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "origin", "HEAD"], cwd=ROOT, check=True)
    print("pushed; Vercel will redeploy", flush=True)
    return True


def take_lock() -> bool:
    """One run at a time: a weekend pull can outlast the gap between two cron ticks."""
    if LOCK.exists():
        age = time.time() - LOCK.stat().st_mtime
        if age < LOCK_STALE_S:
            print(f"another run started {age / 60:.0f} min ago ({LOCK.name}); skipping", flush=True)
            return False
        print(f"ignoring stale lock ({age / 3600:.1f}h old)", flush=True)
    LOCK.write_text(f"{os.getpid()} {pd.Timestamp.utcnow():%Y-%m-%d %H:%M:%S}Z\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--push", action="store_true", help="commit and push the regenerated data")
    ap.add_argument("--dry-run", action="store_true", help="report what is due, change nothing")
    ap.add_argument("--force", action="store_true", help="run even if nothing new is due")
    args = ap.parse_args()

    stamp = pd.Timestamp.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    due = due_sessions(args.year)
    if not due and not args.force:
        print(f"[{stamp}] nothing due", flush=True)
        return 0

    what = ", ".join(f"R{r:02d} {s}" for r, s in due) or "(forced)"
    print(f"[{stamp}] due: {what}", flush=True)
    if args.dry_run:
        return 0
    if not take_lock():
        return 0

    try:
        # --in-progress also stores the sessions of a weekend whose race has not run yet.
        run("backfill", ["scripts/backfill.py", "--years", str(args.year), "--in-progress"])
        run("backtest", ["scripts/backtest.py", "--year", str(args.year)])
        run("export", ["scripts/export_site.py"])
        if args.push:
            publish(what)
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}", flush=True)
        return 1
    finally:
        LOCK.unlink(missing_ok=True)
    print(f"\n[{pd.Timestamp.utcnow():%Y-%m-%d %H:%M:%SZ}] done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
