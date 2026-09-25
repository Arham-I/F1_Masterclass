"""FastF1 access. The only module that talks to FastF1 (live or historical).

Everything downstream works from derived parquet (see ``store.py``), so the deployed
app never needs FastF1 or network access.

The event-match guard exists because the alternative library we evaluated (tif1) silently
returned a *different race's* data for some events. FastF1 did not, but a wrong-race row
would quietly corrupt every downstream feature, so every load is verified.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import fastf1
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / ".fastf1_cache"

_SESSION_COLS = ["Session1", "Session2", "Session3", "Session4", "Session5"]

_cache_ready = False


class EventMismatchError(RuntimeError):
    """FastF1 returned a different event than the one requested."""


def _enable_cache() -> None:
    global _cache_ready
    if _cache_ready:
        return
    CACHE_DIR.mkdir(exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    logging.getLogger("fastf1").setLevel(logging.ERROR)
    _cache_ready = True


def get_schedule(year: int) -> pd.DataFrame:
    """Race weekends for ``year`` (testing excluded), keyed by RoundNumber."""
    _enable_cache()
    sched = fastf1.get_event_schedule(year, include_testing=False)
    return sched[sched.RoundNumber > 0].reset_index(drop=True)


def completed_rounds(year: int, today: date | None = None) -> list[int]:
    """Rounds whose race date is strictly before ``today``."""
    today = today or date.today()
    sched = get_schedule(year)
    done = sched[pd.to_datetime(sched.EventDate).dt.date < today]
    return [int(r) for r in done.RoundNumber]


# A session's data is on FastF1 some time after it ends; practice/qualifying last about an hour.
SESSION_READY_AFTER = pd.Timedelta(hours=2)


def finished_sessions(schedule_row: pd.Series, now: pd.Timestamp | None = None) -> list[str]:
    """Sessions of a weekend whose data should be available by ``now`` (UTC), in running order.
    Never includes the Race: an in-progress weekend is exactly one whose race is still to come."""
    now = now if now is not None else pd.Timestamp.now(tz="UTC").tz_localize(None)
    out = []
    for i in range(1, 6):
        name, start = schedule_row.get(f"Session{i}"), schedule_row.get(f"Session{i}DateUtc")
        if isinstance(name, str) and name and name != "Race" and pd.notna(start) \
                and pd.Timestamp(start).tz_localize(None) + SESSION_READY_AFTER <= now:
            out.append(name)
    return out


def weekend_sessions(schedule_row: pd.Series) -> list[str]:
    """Session names for a weekend, in running order.

    Read from the schedule instead of hard-coding formats: sprint weekends are labelled
    three different ways across 2022-2026, but Session1..5 is always chronological.
    """
    return [str(schedule_row[c]) for c in _SESSION_COLS if pd.notna(schedule_row[c])]


def check_event_match(schedule_row: pd.Series, loaded_event: pd.Series) -> None:
    """Raise if the loaded event is not the scheduled one.

    Keyed on RoundNumber + Location, not the event name: names collide or drift (2026 R16
    is "Bahrain Grand Prix" at Kuala Lumpur; R7 "Barcelona" and R14 "Spanish" are both Spain).
    """
    want = (int(schedule_row["RoundNumber"]), str(schedule_row["Location"]))
    got = (int(loaded_event["RoundNumber"]), str(loaded_event["Location"]))
    if want != got:
        raise EventMismatchError(
            f"requested round {want[0]} ({want[1]}) but FastF1 returned "
            f"round {got[0]} ({got[1]}, {loaded_event['EventName']})"
        )


def load_session(year: int, round_number: int, session_name: str):
    """Load one session (laps + weather, no telemetry), verified to be the requested event."""
    _enable_cache()
    sched = get_schedule(year)
    rows = sched[sched.RoundNumber == round_number]
    if rows.empty:
        raise ValueError(f"no round {round_number} in {year} schedule")
    row = rows.iloc[0]

    session = fastf1.get_session(year, round_number, session_name)
    session.load(laps=True, telemetry=False, weather=True, messages=False)

    check_event_match(row, session.event)
    if len(session.laps) == 0:
        raise EventMismatchError(
            f"{year} R{round_number} {session_name}: loaded but contains no laps"
        )
    return session
