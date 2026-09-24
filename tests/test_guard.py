"""The event-match guard is a regression test for a real failure: tif1 silently returned
Australia's data when asked for Monza (and Miami's for Imola). No error, valid-looking data."""
from pathlib import Path

import pandas as pd
import pytest

from f1cc.data import CACHE_DIR, EventMismatchError, check_event_match, weekend_sessions


def _fastf1_cache_available() -> bool:
    return Path(CACHE_DIR).exists() and any(Path(CACHE_DIR).iterdir())


def row(rnd, location, name="X"):
    return pd.Series({"RoundNumber": rnd, "Location": location, "EventName": name})


def test_matching_event_passes():
    check_event_match(row(16, "Monza", "Italian Grand Prix"), row(16, "Monza", "Italian Grand Prix"))


def test_tif1_failure_mode_monza_returns_australia_is_caught():
    monza = row(16, "Monza", "Italian Grand Prix")
    australia = row(1, "Melbourne", "Australian Grand Prix")
    with pytest.raises(EventMismatchError, match="round 16"):
        check_event_match(monza, australia)


def test_keyed_on_round_and_location_not_name():
    # 2026 quirk: R16 is named "Bahrain Grand Prix" but is held at Kuala Lumpur.
    sched = row(16, "Kuala Lumpur", "Bahrain Grand Prix")
    check_event_match(sched, row(16, "Kuala Lumpur", "Renamed Grand Prix"))          # name drift is fine
    with pytest.raises(EventMismatchError):
        check_event_match(sched, row(4, "Sakhir", "Bahrain Grand Prix"))           # same name, wrong race


def test_same_country_events_are_distinguished():
    # 2026 has two Spanish events (R7 Barcelona, R14 Madrid).
    with pytest.raises(EventMismatchError):
        check_event_match(row(14, "Madrid"), row(7, "Barcelona"))


def test_weekend_sessions_follow_schedule_order_for_any_format():
    conventional = pd.Series({"Session1": "Practice 1", "Session2": "Practice 2", "Session3": "Practice 3",
                              "Session4": "Qualifying", "Session5": "Race"})
    sprint = pd.Series({"Session1": "Practice 1", "Session2": "Sprint Qualifying", "Session3": "Sprint",
                        "Session4": "Qualifying", "Session5": "Race"})
    assert weekend_sessions(conventional)[-2:] == ["Qualifying", "Race"]
    assert weekend_sessions(sprint)[1] == "Sprint Qualifying"


# --- generalization against the REAL schedules (no network: FastF1 caches these) ------------
# Confirmed the sprint pre-qualifying session is named differently release to release:
# 2022 = "Sprint" only (no separate sprint-quali session existed yet), 2023 = "Sprint Shootout",
# 2024-2026 = "Sprint Qualifying". The synthetic test above only proves the *logic* handles one
# shape; this proves weekend_sessions() actually copes with all the real ones without hardcoding
# any label.
REAL_SPRINT_LABEL_BY_YEAR = {2022: {"Sprint"}, 2023: {"Sprint", "Sprint Shootout"},
                            2024: {"Sprint", "Sprint Qualifying"}, 2025: {"Sprint", "Sprint Qualifying"},
                            2026: {"Sprint", "Sprint Qualifying"}}


@pytest.mark.skipif(not _fastf1_cache_available(), reason="FastF1 cache not warmed")
@pytest.mark.parametrize("year", sorted(REAL_SPRINT_LABEL_BY_YEAR))
def test_weekend_sessions_handles_every_real_schedule_row(year):
    from f1cc.data import get_schedule
    sched = get_schedule(year)
    seen_sprint_labels = set()
    for _, sched_row in sched.iterrows():
        expected_len = sched_row[["Session1", "Session2", "Session3", "Session4", "Session5"]].notna().sum()
        sessions = weekend_sessions(sched_row)
        assert len(sessions) == expected_len, f"{year} R{sched_row.RoundNumber}: dropped a session"
        assert sessions[-1] == "Race"
        assert all(isinstance(s, str) and s for s in sessions)
        seen_sprint_labels |= set(sessions) - {"Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"}
    assert seen_sprint_labels == REAL_SPRINT_LABEL_BY_YEAR[year]
