"""The backfill runs unattended for hours, so its rate-limit handling has to be right.

Regression: FastF1 caps at ~500 API calls/hour. Once tripped, every later session errored in
milliseconds and a naive backfill 'finished' having fetched almost nothing (338 silent skips).
"""
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "backfill.py"


class RateLimitExceededError(Exception):
    """Same class name FastF1 uses; the script matches on the name."""


@pytest.fixture
def bf(monkeypatch):
    spec = importlib.util.spec_from_file_location("backfill_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.features, "extract", lambda s, y, r, i: ("F", "L", "S"))
    return mod


def test_waits_out_the_rate_limit_then_succeeds(bf, monkeypatch):
    calls = []

    def load(y, r, s):
        calls.append(1)
        if len(calls) < 3:
            raise RateLimitExceededError("any API: 500 calls/h")
        return "SESSION"

    sleeps = []
    monkeypatch.setattr(bf.data, "load_session", load)
    monkeypatch.setattr(bf.time, "sleep", sleeps.append)

    assert bf._load_and_extract(2025, 2, "Qualifying", 3) == ("F", "L", "S")
    assert len(calls) == 3 and sleeps == [bf.RATE_LIMIT_WAIT_S] * 2


def test_other_errors_fail_immediately_without_waiting(bf, monkeypatch):
    sleeps = []
    monkeypatch.setattr(bf.data, "load_session", lambda *a: (_ for _ in ()).throw(ValueError("bad")))
    monkeypatch.setattr(bf.time, "sleep", sleeps.append)

    with pytest.raises(ValueError):
        bf._load_and_extract(2025, 2, "Qualifying", 3)
    assert sleeps == []


def test_gives_up_after_max_waits_instead_of_hanging_forever(bf, monkeypatch):
    sleeps = []
    monkeypatch.setattr(bf.data, "load_session",
                        lambda *a: (_ for _ in ()).throw(RateLimitExceededError("500 calls/h")))
    monkeypatch.setattr(bf.time, "sleep", sleeps.append)

    with pytest.raises(RateLimitExceededError):
        bf._load_and_extract(2025, 2, "Qualifying", 3)
    assert len(sleeps) == bf.RATE_LIMIT_MAX_WAITS
