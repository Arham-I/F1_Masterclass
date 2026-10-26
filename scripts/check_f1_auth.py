"""Check that the Formula 1 account sign-in works and that a session will load.

    .venv/bin/python scripts/check_f1_auth.py

Run this after scripts/set_f1_credentials.sh, and whenever an unattended update starts failing:
it separates "the credentials are wrong" from "the session isn't published yet".
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastf1.internals import f1account  # noqa: E402

from f1cc import data  # noqa: E402


def main() -> int:
    data._setup()                      # loads the credentials file into the environment
    user = os.environ.get("F1_USERNAME")
    if not user:
        print(f"no credentials: run scripts/set_f1_credentials.sh (expected {data.CREDENTIALS_FILE})")
        return 1
    print(f"account   {user}")
    print(f"method    {f1account.get_auth_method()}")

    try:
        token = f1account.get_token()
    except Exception as e:
        print(f"SIGN-IN FAILED  {type(e).__name__}: {e}")
        return 1
    expires = dt.datetime.fromtimestamp(token.expires_at)
    print(f"token     valid until {expires:%Y-%m-%d %H:%M} local")

    # A token is not proof of access: an account without a subscription signs in and still gets 401.
    year, rnd, sname = 2026, 1, "Qualifying"
    try:
        session = data.load_session(year, rnd, sname)
        laps = len(session.laps)
    except Exception as e:
        print(f"SESSION LOAD FAILED  {year} R{rnd:02d} {sname}: {type(e).__name__}: {str(e)[:200]}")
        return 1
    print(f"data      {year} R{rnd:02d} {sname}: {laps} laps loaded")
    print("\nauthentication ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
