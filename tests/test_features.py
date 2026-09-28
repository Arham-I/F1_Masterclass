"""Feature logic on synthetic sessions (offline). The point is to pin down the filtering rules
that a real-data run exposed: e.g. the 107% rule must not delete practice long-run laps."""
import numpy as np
import pandas as pd

from f1cc.features import extract


class FakeSession:
    def __init__(self, laps, results, name="Practice 2"):
        self.laps, self.results, self.name = laps, results, name
        self.event = pd.Series({"Location": "Madrid", "EventName": "Spanish Grand Prix",
                                "EventDate": pd.Timestamp("2026-09-13")})


def stint(driver, team, compound, base, n=8, stint_no=1, start_lap=1, deg=0.0):
    rows = []
    for i in range(n):
        rows.append(dict(
            Driver=driver, Team=team, LapNumber=start_lap + i, Stint=stint_no, Compound=compound,
            TyreLife=i + 1, LapTime=pd.Timedelta(seconds=base + deg * i),
            Sector1Time=pd.Timedelta(seconds=30), Sector2Time=pd.Timedelta(seconds=30),
            Sector3Time=pd.Timedelta(seconds=base - 60), PitInTime=pd.NaT, PitOutTime=pd.NaT,
            TrackStatus="1", IsAccurate=True, Deleted=False))
    return rows


def results_for(drivers):
    no_time = pd.to_timedelta([pd.NaT] * len(drivers))   # real FastF1 Q1-Q3 are timedeltas
    return pd.DataFrame({
        "Abbreviation": drivers, "TeamName": [f"Team{d}" for d in drivers],
        "TeamColor": ["FF0000"] * len(drivers), "Position": np.nan, "GridPosition": np.nan,
        "Status": "", "Q1": no_time, "Q2": no_time, "Q3": no_time})


def build(rows, name="Practice 2"):
    laps = pd.DataFrame(rows)
    return FakeSession(laps, results_for(sorted(laps["Driver"].unique())), name)


def test_longrun_delta_is_compound_neutral():
    # Medium runners at 90.0/90.2/90.4, hard runners exactly +1.0s slower on the same pattern.
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b)
    for d, b in zip("XYZ", (91.0, 91.2, 91.4)):
        rows += stint(d, "T", "HARD", b)
    f, laps, _ = extract(build(rows), 2026, 14, 1)
    f = f.set_index("driver")
    assert np.isclose(f.loc["A", "longrun_delta_s"], f.loc["X", "longrun_delta_s"])
    assert np.isclose(f.loc["A", "longrun_delta_s"], -0.2)
    assert f.loc["A", "longrun_rank"] == 1 and f.loc["A", "longrun_gap_s"] == 0


def test_practice_long_runs_are_not_deleted_by_the_107_percent_rule():
    # One flying lap at 80s, long runs at ~90s (12% slower): all must survive in practice.
    rows = stint("A", "T", "SOFT", 80.0, n=1, stint_no=1)
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b, stint_no=2, start_lap=5)
    f, laps, _ = extract(build(rows, "Practice 2"), 2026, 14, 1)
    assert (f["longrun_n"] > 0).all()


def test_race_sessions_do_apply_the_slow_lap_rule_and_skip_lap_one():
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b, n=8)
    rows[0]["LapTime"] = pd.Timedelta(seconds=140)      # lap 1 of driver A: standing start / slow
    _, laps, _ = extract(build(rows, "Race"), 2026, 14, 4)
    assert not ((laps["driver"] == "A") & (laps["lap"] == 1)).any()
    assert laps["lap_time_s"].max() < 100


def test_pit_laps_and_non_green_laps_are_excluded():
    rows = stint("A", "T", "MEDIUM", 90.0, n=8)
    rows[2]["PitInTime"] = pd.Timedelta(seconds=1)
    rows[4]["TrackStatus"] = "2"                          # yellow
    for d, b in zip("BC", (90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b, n=8)
    _, laps, _ = extract(build(rows), 2026, 14, 1)
    a = set(laps[laps["driver"] == "A"]["lap"])
    assert 3 not in a and 5 not in a and len(a) == 6


def test_push_lap_inside_a_stint_does_not_contaminate_the_long_run():
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b, n=8)
    rows[3]["LapTime"] = pd.Timedelta(seconds=80.0)       # a flying lap in A's stint
    _, laps, _ = extract(build(rows), 2026, 14, 1)
    assert 4 not in set(laps[(laps["driver"] == "A") & laps["longrun_delta_s"].notna()]["lap"])


def test_short_stints_are_not_long_runs():
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b, n=3)
    f, _, _ = extract(build(rows), 2026, 14, 1)
    assert (f["longrun_n"] == 0).all() and f["longrun_delta_s"].isna().all()


def test_team_falls_back_to_results_when_laps_omit_it():
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, np.nan, "MEDIUM", b)               # FastF1 dropped laps.Team for the session
    f, laps, _ = extract(build(rows), 2026, 14, 0)
    assert (f["team"] != "").all() and f["team"].iloc[0] == "TeamA"
    assert (laps["team"] != "").all()


def test_repair_teams_uses_same_round_then_same_year():
    from f1cc.features import FALLBACK_TEAM_COLOR, repair_teams
    def row(rnd, sess, drv, team, color):
        return dict(year=2026, round=rnd, session=sess, driver=drv, team=team, team_color=color)
    f = pd.DataFrame([
        row(5, "Practice 1", "AAA", "", FALLBACK_TEAM_COLOR),     # blank; same round has P2 -> repaired from it
        row(5, "Qualifying", "AAA", "Ferrari", "#ED1131"),
        row(7, "Practice 1", "AAA", "", FALLBACK_TEAM_COLOR),     # whole weekend blank -> falls back to year
        row(7, "Qualifying", "AAA", "", FALLBACK_TEAM_COLOR),
        row(9, "Qualifying", "BBB", "McLaren", "#F47600"),
    ])
    laps = pd.DataFrame([dict(year=2026, round=5, driver="AAA", team=""),
                         dict(year=2026, round=7, driver="AAA", team="")])
    f2, laps2 = repair_teams(f, laps)
    assert list(f2["team"][:4]) == ["Ferrari"] * 4
    assert list(f2["team_color"][:4]) == ["#ED1131"] * 4
    assert list(laps2["team"]) == ["Ferrari", "Ferrari"]
    assert repair_teams(f2, laps2)[0].equals(f2)                    # idempotent


def test_repair_teams_fixes_missing_colour_even_when_team_name_is_present():
    # 2024 R1/R12/R16 bug: results.TeamColor empty for a whole session, but TeamName present.
    from f1cc.features import FALLBACK_TEAM_COLOR, repair_teams
    def row(rnd, sess, drv, team, color):
        return dict(year=2024, round=rnd, session=sess, driver=drv, team=team, team_color=color)
    f = pd.DataFrame([
        row(1, "Practice 2", "AAA", "Ferrari", FALLBACK_TEAM_COLOR),   # name present, colour missing
        row(1, "Qualifying", "AAA", "Ferrari", "#E80020"),
        row(1, "Practice 2", "BBB", "McLaren", "#FF8000"),             # already fine, must not change
    ])
    f2, _ = repair_teams(f)
    assert f2.loc[0, "team_color"] == "#E80020"
    assert f2.loc[2, "team_color"] == "#FF8000"


def test_team_color_hex_is_case_normalized():
    from f1cc.features import _team_color
    assert _team_color("e8002d") == _team_color("E8002D") == "#E8002D"


def test_gaps_and_rank_use_best_valid_lap():
    rows = []
    for d, b in zip("ABC", (90.0, 90.2, 90.4)):
        rows += stint(d, "T", "MEDIUM", b)
    f, _, _ = extract(build(rows), 2026, 14, 1)
    f = f.set_index("driver")
    assert f.loc["A", "gap_to_best_s"] == 0 and np.isclose(f.loc["C", "gap_to_best_s"], 0.4)
    assert list(f.sort_values("pace_rank").index) == ["A", "B", "C"]


# --- on-track overtakes -------------------------------------------------------------------
class _RaceSession:
    def __init__(self, laps):
        self.laps = laps
        self.event = pd.Series({"Location": "Testville"})


def _race_laps(rows):
    df = pd.DataFrame(rows, columns=["Driver", "LapNumber", "Position", "PitInTime", "PitOutTime", "TrackStatus"])
    for c in ("PitInTime", "PitOutTime"):
        df[c] = pd.to_timedelta(df[c])
    return df


def test_race_overtakes_counts_on_track_swaps_only():
    from f1cc.features import race_overtakes
    T = pd.Timedelta("1h")
    rows = []
    for lap in range(1, 8):
        a_pos, b_pos, c_pos = (1, 2, 3)
        if lap >= 4: a_pos, b_pos = 2, 1                  # lap 4: B passes A on track -> 1 overtake
        if lap >= 6: b_pos, c_pos = 3, 2                  # lap 6: C "passes" B because B pits -> not counted
        pit_b = T if lap == 6 else None
        status = "4" if lap == 5 else "1"                 # lap 5 under safety car
        rows += [("A", lap, a_pos, None, None, status), ("B", lap, b_pos, pit_b, None, status),
                 ("C", lap, c_pos, None, None, status)]
    out = race_overtakes(_RaceSession(_race_laps(rows)), 2099, 1)
    assert out["overtakes"].iloc[0] == 1
    # counted laps: 3, 4 and 7 (lap 5 is under the safety car, lap 6 follows it; on lap 7 only A and C
    # are compared because B pitted on lap 6)
    assert out["green_laps"].iloc[0] == 3
