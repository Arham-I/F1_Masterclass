"""Replay cutoff: nothing after the current session may ever reach a consumer."""
import pandas as pd
import pytest

from f1cc.replay import Cutoff, Weekend, apply_cutoff

SESSIONS = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]


@pytest.fixture
def features():
    rows = []
    for year, rnd in [(2026, 14), (2026, 13)]:           # two weekends, so we also test isolation
        for idx, s in enumerate(SESSIONS):
            for drv in ("AAA", "BBB"):
                rows.append(dict(year=year, round=rnd, session=s, session_idx=idx, driver=drv,
                                 event_name="E", location="L", event_date="2026-09-13"))
    return pd.DataFrame(rows)


@pytest.fixture
def weekend(features):
    return Weekend.from_features(features, 2026, 14)


def test_weekend_order_and_race_is_never_replayable(weekend):
    assert weekend.sessions == tuple(SESSIONS)
    assert "Race" not in weekend.replayable


def test_nothing_visible_at_start(features, weekend):
    assert apply_cutoff(features, Cutoff(weekend, 0)).empty


@pytest.mark.parametrize("revealed", [1, 2, 3, 4])
def test_cutoff_never_leaks_a_later_session(features, weekend, revealed):
    out = apply_cutoff(features, Cutoff(weekend, revealed))
    assert set(out["session"]) == set(SESSIONS[:revealed])
    later = set(SESSIONS[revealed:])
    assert not (set(out["session"]) & later)


def test_the_race_result_is_never_reachable_even_when_fully_revealed(features, weekend):
    full = Cutoff(weekend, len(weekend.replayable))
    assert full.is_done
    assert "Race" not in set(apply_cutoff(features, full)["session"])


def test_cutoff_is_scoped_to_its_own_weekend(features, weekend):
    out = apply_cutoff(features, Cutoff(weekend, 4))
    assert set(out["round"]) == {14}


def test_advance_and_reset(weekend):
    c = Cutoff(weekend, 0)
    assert c.current is None and c.next_session == "Practice 1"
    c = c.advance().advance()
    assert c.current == "Practice 2" and c.visible == ("Practice 1", "Practice 2")
    assert c.reset().revealed == 0


def test_advance_stops_at_the_end(weekend):
    c = Cutoff(weekend, len(weekend.replayable))
    assert c.advance() is c and c.next_session is None


def test_out_of_range_cutoff_rejected(weekend):
    with pytest.raises(ValueError):
        Cutoff(weekend, 99)
