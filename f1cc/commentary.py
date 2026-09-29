"""Short written commentary for each replay step and for the race result.

Every sentence is built from numbers computed here from the stored data - nothing is typed in
by hand and nothing is invented - so the text can never disagree with the charts. The inputs
are exactly what the replay is allowed to see at that point (the revealed sessions, the
prediction made at that stage, and races *before* this weekend), so the commentary cannot leak
the result either.
"""
from __future__ import annotations

import pandas as pd

from f1cc.predict.base import finished

SHORT = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Sprint Qualifying": "Sprint Qualifying",
         "Sprint": "the Sprint", "Qualifying": "Qualifying"}


def lap(seconds: float) -> str:
    m, s = divmod(float(seconds), 60)
    return f"{int(m)}:{s:06.3f}"


def pct(p: float) -> str:
    return f"{p * 100:.1f}%"


def a_pct(p: float) -> str:
    """'a 45.4%' / 'an 86.3%' / 'an 11.0%' - the article follows how the number is spoken."""
    text = pct(p)
    return ("an " if text.startswith(("8", "11", "18")) else "a ") + text


def gap(seconds: float) -> str:
    return f"{seconds:.3f}s"


def _name(names: dict[str, str], code: str) -> str:
    return names.get(code, code)


def session_notes(session: str, rows: pd.DataFrame, names: dict[str, str]) -> list[str]:
    """What happened in the session itself: who was fastest / won, and by how much."""
    notes: list[str] = []
    label = SHORT.get(session, session)
    if session == "Sprint" and rows["position"].notna().any():
        top = rows.dropna(subset=["position"]).sort_values("position")
        podium = [_name(names, d) for d in top["driver"].head(3)]
        if len(podium) == 3:
            notes.append(f"{podium[0]} won the Sprint ahead of {podium[1]} and {podium[2]}.")
        return notes
    timed = rows.dropna(subset=["gap_to_best_s"]).sort_values("gap_to_best_s")
    if len(timed) < 2:
        return notes
    first, second = timed.iloc[0], timed.iloc[1]
    margin = float(second["gap_to_best_s"])
    close = ", a tiny margin" if margin < 0.05 else ""
    if session == "Qualifying":
        notes.append(f"{_name(names, first['driver'])} takes pole with a {lap(first['best_lap_s'])}, "
                     f"{gap(margin)} faster than {_name(names, second['driver'])}{close}.")
        if first["team"] == second["team"]:
            notes.append(f"{first['team']} lock out the front row.")
    elif session == "Sprint Qualifying":
        notes.append(f"{_name(names, first['driver'])} was fastest in Sprint Qualifying, "
                     f"{gap(margin)} ahead of {_name(names, second['driver'])}{close}.")
    else:
        notes.append(f"{_name(names, first['driver'])} ({first['team']}) topped {label} with a "
                     f"{lap(first['best_lap_s'])}, {gap(margin)} clear of {_name(names, second['driver'])}{close}.")
        lr = rows.dropna(subset=["longrun_delta_s"]).sort_values("longrun_delta_s")
        if len(lr) >= 5:
            best = lr.iloc[0]
            notes.append(f"On the long race-simulation runs, {_name(names, best['driver'])} looked strongest: "
                         f"{abs(best['longrun_delta_s']):.2f}s a lap quicker than the typical car on the same tyre.")
    return notes


def prediction_notes(now: pd.DataFrame, prev: pd.DataFrame | None, names: dict[str, str]) -> list[str]:
    """The favourite, how the picture moved since the last session, and how sure we are."""
    notes: list[str] = []
    fav = now.sort_values("expected_pos").iloc[0]      # predicted winner (same pick the backtest scores)
    line = f"Predicted winner: {_name(names, fav['driver'])}, with {a_pct(fav['p_win'])} chance to win"
    if prev is not None and fav["driver"] in set(prev["driver"]):
        before = float(prev.set_index("driver").loc[fav["driver"], "p_win"])
        if abs(fav["p_win"] - before) >= 0.02:
            line += f" ({'up' if fav['p_win'] > before else 'down'} from {pct(before)})"
    notes.append(line + ".")
    if prev is not None:
        moved = now.merge(prev[["driver", "expected_pos"]], on="driver", suffixes=("", "_prev"))
        moved["change"] = moved["expected_pos_prev"] - moved["expected_pos"]
        if len(moved) and moved["change"].abs().max() >= 3:
            m = moved.loc[moved["change"].abs().idxmax()]
            verb = "climbs" if m["change"] > 0 else "drops"
            notes.append(f"Biggest mover: {_name(names, m['driver'])} {verb} from a predicted "
                         f"P{int(m['expected_pos_prev'])} to P{int(m['expected_pos'])}.")
        was, now_s = float(prev["sigma"].mean()), float(now["sigma"].mean())
        if now_s < was - 0.05:
            notes.append(f"The picture is sharper: a typical finisher is now expected within ±{now_s:.1f} places "
                         f"of our prediction (±{was:.1f} before).")
    return notes


def pole_record(features: pd.DataFrame, year: int, round_number: int) -> str | None:
    """How often pole became a win in this season's races *before* this one."""
    f = features[(features["year"] == year) & (features["round"] < round_number)]
    q = f[f["session"] == "Qualifying"].dropna(subset=["position"])
    race = f[f["session"] == "Race"].dropna(subset=["position"])
    rounds = sorted(set(q["round"]) & set(race["round"]))
    if len(rounds) < 3:
        return None
    pole = q[q["position"] == 1].set_index("round")["driver"]
    win = race[race["position"] == 1].set_index("round")["driver"]
    hits = sum(pole.get(r) == win.get(r) for r in rounds)
    return f"So far this season, pole has turned into victory in {hits} of {len(rounds)} races."


def race_notes(df: pd.DataFrame, names: dict[str, str]) -> list[str]:
    """``df``: one row per driver with expected_pos, p_win, actual, grid, status (after Qualifying)."""
    notes: list[str] = []
    fin = finished(df["status"].fillna(""))
    winner = df.loc[df["actual"].idxmin()]
    fav = df.loc[df["expected_pos"].idxmin()]
    if winner["driver"] == fav["driver"]:
        notes.append(f"{_name(names, winner['driver'])} won, as predicted: we gave them {pct(winner['p_win'])}.")
    else:
        notes.append(f"{_name(names, winner['driver'])} won. We had given them {pct(winner['p_win'])}; our predicted "
                     f"winner was {_name(names, fav['driver'])} ({pct(fav['p_win'])}).")
    picked = set(df.nsmallest(3, "expected_pos")["driver"]) & set(df.nsmallest(3, "actual")["driver"])
    notes.append(f"We called {len(picked)} of the 3 podium finishers.")
    ok = df[fin].assign(beat=lambda d: d["expected_pos"] - d["actual"])
    if len(ok) and ok["beat"].max() >= 4:
        b = ok.loc[ok["beat"].idxmax()]
        start = f" from P{int(b['grid'])} on the grid" if pd.notna(b.get("grid")) and b["grid"] > 0 else ""
        notes.append(f"Beat the prediction by most: {_name(names, b['driver'])}, P{int(b['actual'])}{start} "
                     f"(we said P{int(b['expected_pos'])}).")
    out = df[~fin]
    if len(out):
        notes.append(f"{len(out)} {'car' if len(out) == 1 else 'cars'} did not finish: "
                     + ", ".join(_name(names, d) for d in out.sort_values("actual")["driver"]) + ".")
    return notes
