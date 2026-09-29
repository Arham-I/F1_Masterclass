"""Export the stored 2026 data as JSON for the website in web/ (Next.js on Vercel).

Run after backfill + backtest:
    python scripts/backfill.py --years 2026 [--in-progress]
    python scripts/backtest.py
    python scripts/export_site.py

The race calendar and driver names come from FastF1's local cache (no network needed once the
backfill has run) and are saved to data/schedule_2026.csv and data/drivers_2026.csv, so the export
still works on a machine without FastF1 by reusing those files (--no-fastf1).
"""
import argparse
import json
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from f1cc import site_export, store  # noqa: E402

warnings.filterwarnings("ignore")
WEB = store.ROOT / "web"
SCHEDULE_FILE = store.DATA_DIR / f"schedule_{site_export.SITE_YEAR}.csv"
DRIVERS_FILE = store.DATA_DIR / f"drivers_{site_export.SITE_YEAR}.csv"


def _utc(ts) -> str | None:
    return None if pd.isna(ts) else pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def refresh_meta(year: int) -> None:
    """Calendar (all rounds, session start times in UTC) and driver names, from the FastF1 cache."""
    import fastf1
    from f1cc import data

    data._enable_cache()
    sched = data.get_schedule(year)
    rows = []
    for r in sched.itertuples(index=False):
        sessions = [{"name": getattr(r, f"Session{i}"), "start_utc": _utc(getattr(r, f"Session{i}DateUtc"))}
                    for i in range(1, 6) if isinstance(getattr(r, f"Session{i}"), str) and getattr(r, f"Session{i}")]
        rows.append({"round": int(r.RoundNumber), "name": r.EventName, "location": r.Location,
                     "country": r.Country, "format": "sprint" if "sprint" in r.EventFormat else "conventional",
                     "sessions": json.dumps(sessions)})
    pd.DataFrame(rows).to_csv(SCHEDULE_FILE, index=False)

    f = store.read("features", [year])
    names = {}
    for (rd, session) in f[["round", "session"]].drop_duplicates().itertuples(index=False):
        try:
            s = fastf1.get_session(year, int(rd), session)
            s.load(laps=False, telemetry=False, weather=False, messages=False)
        except Exception as e:  # a session missing from the cache just keeps codes
            print(f"  names: R{rd} {session} skipped ({type(e).__name__})")
            continue
        for d in s.results.itertuples(index=False):
            if isinstance(d.Abbreviation, str) and d.Abbreviation:
                names[d.Abbreviation] = {"name": f"{d.FirstName} {d.LastName}".strip(),
                                         "number": str(d.DriverNumber)}
    pd.DataFrame([{"driver": k, **v} for k, v in sorted(names.items())]).to_csv(DRIVERS_FILE, index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fastf1", action="store_true", help="reuse the saved calendar and names")
    args = ap.parse_args()
    if not args.no_fastf1:
        try:
            refresh_meta(site_export.SITE_YEAR)
        except Exception as e:
            # Unattended (scripts/auto_update.py), a FastF1 hiccup must not block the export: the
            # calendar and names change rarely, so the saved copies are almost always current.
            if not (SCHEDULE_FILE.exists() and DRIVERS_FILE.exists()):
                raise
            print(f"calendar/names refresh failed ({type(e).__name__}); using the saved copies")
    schedule = pd.read_csv(SCHEDULE_FILE)
    names = {r.driver: {"name": r["name"], "number": str(r["number"])}
             for _, r in pd.read_csv(DRIVERS_FILE, dtype={"number": str}).assign(driver=lambda d: d["driver"]).iterrows()}
    written = site_export.export(WEB, schedule, names)
    size = sum(p.stat().st_size for p in written)
    print(f"wrote {len(written)} files ({size / 1024:.0f} KB) under {WEB.relative_to(store.ROOT)}/")


if __name__ == "__main__":
    main()
