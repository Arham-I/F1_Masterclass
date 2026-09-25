"""Turn a loaded FastF1 session into three compact tables.

  features - one row per driver per session (pace, gaps, long-run pace, degradation)
  laps     - clean laps only, for the long-run distribution chart
  stints   - every stint, for the tyre-strategy chart

Design rule: pace is expressed *relative to the field in the same session* (gaps, ranks,
compound-neutral deltas), never as absolute lap times. Absolute times do not transfer across
regulation eras or even across circuits; relative pace does.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_RUN = 5                    # clean laps for a stint to count as a long run
SLOW_LAP_FACTOR = 1.07         # race-like sessions only: drop laps slower than 107% of best clean lap
STINT_BAND = (0.96, 1.04)      # keep laps within this band of their own stint median
MIN_DRIVERS_PER_COMPOUND = 3   # need a field to define a per-compound reference pace
DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}
RACE_LIKE = {"Race", "Sprint"}

FALLBACK_TEAM_COLOR = "#8A8D93"


def _team_color(raw) -> str:
    raw = "" if raw is None or (isinstance(raw, float) and np.isnan(raw)) else str(raw).strip()
    return f"#{raw.lstrip('#').upper()}" if raw else FALLBACK_TEAM_COLOR


def _secs(td: pd.Series) -> pd.Series:
    return pd.to_timedelta(td).dt.total_seconds()


def _prepare_laps(session) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Return (laps with numeric columns, timed mask, clean mask)."""
    laps = session.laps.copy().reset_index(drop=True)
    laps["lap_time_s"] = _secs(laps["LapTime"])
    for k in (1, 2, 3):
        laps[f"s{k}_s"] = _secs(laps[f"Sector{k}Time"])

    deleted = laps["Deleted"].eq(True)
    accurate = laps["IsAccurate"].eq(True)
    timed = laps["lap_time_s"].notna() & accurate & ~deleted

    in_or_out = laps["PitInTime"].notna() | laps["PitOutTime"].notna()
    green = laps["TrackStatus"].astype(str) == "1"
    standing_start = pd.Series(False, index=laps.index)
    if session.name in RACE_LIKE:
        standing_start = laps["LapNumber"] == 1

    clean = timed & ~in_or_out & green & ~standing_start
    # The 107% rule is a race/quali notion. In practice, long-run laps are legitimately several
    # percent off a push lap, so applying it there deletes exactly the laps we want; the
    # per-stint band in _long_runs handles cool-down laps instead.
    if session.name in RACE_LIKE and clean.any():
        best_clean = laps.loc[clean, "lap_time_s"].min()
        clean &= laps["lap_time_s"] <= best_clean * SLOW_LAP_FACTOR
    return laps, timed, clean


def _long_runs(laps: pd.DataFrame, clean: pd.Series) -> pd.DataFrame:
    """Clean laps belonging to genuine long runs, with a compound-neutral pace delta.

    ``longrun_delta_s`` is a lap's time minus the field's median long-run time on that
    compound, so a driver on softs and one on hards are directly comparable.
    """
    empty = pd.DataFrame(columns=list(laps.columns) + ["longrun_delta_s"])
    c = laps[clean & laps["Compound"].isin(DRY_COMPOUNDS) & laps["Stint"].notna()].copy()
    if c.empty:
        return empty

    key = ["Driver", "Stint"]
    c["_stint_med"] = c.groupby(key)["lap_time_s"].transform("median")
    ratio = c["lap_time_s"] / c["_stint_med"]
    c = c[(ratio >= STINT_BAND[0]) & (ratio <= STINT_BAND[1])].copy()
    c["_run_n"] = c.groupby(key)["lap_time_s"].transform("size")
    lr = c[c["_run_n"] >= MIN_RUN].copy()
    if lr.empty:
        return empty

    lr = lr.copy()
    per_driver = lr.groupby(["Compound", "Driver"])["lap_time_s"].median().reset_index()
    n_drivers = per_driver.groupby("Compound")["Driver"].nunique()
    usable = n_drivers[n_drivers >= MIN_DRIVERS_PER_COMPOUND].index
    if len(usable) == 0:
        return empty
    ref = per_driver[per_driver["Compound"].isin(usable)].groupby("Compound")["lap_time_s"].median()

    lr = lr[lr["Compound"].isin(usable)].copy()
    lr["longrun_delta_s"] = lr["lap_time_s"] - lr["Compound"].map(ref)
    return lr.drop(columns=["_stint_med", "_run_n"])


def _degradation(lr: pd.DataFrame) -> pd.Series:
    """Median per-stint slope of lap time vs lap number (s/lap), per driver.

    Net figure: it includes the fuel-burn gain, so it understates true tyre wear. Fine for
    comparing drivers within a session; not an absolute wear rate.
    """
    slopes = {}
    for (drv, _), g in lr.groupby(["Driver", "Stint"]):
        if len(g) >= MIN_RUN and g["LapNumber"].nunique() >= MIN_RUN:
            slopes.setdefault(drv, []).append(np.polyfit(g["LapNumber"], g["lap_time_s"], 1)[0])
    return pd.Series({d: float(np.median(v)) for d, v in slopes.items()}, dtype=float)


def _stints(laps: pd.DataFrame) -> pd.DataFrame:
    s = laps[laps["Stint"].notna()]
    if s.empty:
        return pd.DataFrame(columns=["driver", "stint", "compound", "lap_start", "lap_end", "n_laps"])

    def _mode(x: pd.Series) -> str:
        x = x.dropna()
        return str(x.mode().iat[0]) if len(x) else "UNKNOWN"

    g = s.groupby(["Driver", "Stint"]).agg(
        compound=("Compound", _mode),
        lap_start=("LapNumber", "min"),
        lap_end=("LapNumber", "max"),
        n_laps=("LapNumber", "size"),
    ).reset_index()
    g = g.rename(columns={"Driver": "driver", "Stint": "stint"})
    g["stint"] = g["stint"].astype(int)
    return g


def repair_teams(features: pd.DataFrame, laps: pd.DataFrame | None = None):
    """Fill blank team / colour using the same driver's other sessions.

    FastF1 sometimes has *no* team data for a whole session (2026 R5 and R7 FP1: both
    laps.Team and results.TeamName are empty), so it cannot be repaired per-session. Needs
    the year's full table: prefer the driver's team in the same round, else their team
    elsewhere that season. Idempotent. Returns (features, laps).

    Team name and team colour are repaired independently: some sessions have every driver's
    colour missing from results.TeamColor while the team *name* is present (seen: 2024 R1
    Practice 2, R12 Practice 2, R16 Practice 3, all ten teams at once), so a colour repair
    gated on "team was also blank" misses them.
    """
    f = features.copy()
    blank_team = f["team"].fillna("").str.strip() == ""
    if blank_team.any():
        known = f[~blank_team]
        by_round = known.groupby(["year", "round", "driver"])["team"].agg(lambda x: x.mode().iat[0])
        by_year = known.groupby(["year", "driver"])["team"].agg(lambda x: x.mode().iat[0])
        f.loc[blank_team, "team"] = [
            by_round.get((y, r, d), by_year.get((y, d), ""))
            for y, r, d in zip(f.loc[blank_team, "year"], f.loc[blank_team, "round"], f.loc[blank_team, "driver"])
        ]

    # Colour follows the team name (now filled in above where possible), regardless of
    # whether the team name itself needed repair.
    fallback_color = f["team_color"] == FALLBACK_TEAM_COLOR
    if fallback_color.any():
        real = f[~fallback_color & (f["team"] != "")]
        color_of = real.groupby(["year", "team"])["team_color"].agg(lambda x: x.mode().iat[0])
        fix = fallback_color & (f["team"] != "")
        f.loc[fix, "team_color"] = [
            color_of.get((y, t), FALLBACK_TEAM_COLOR)
            for y, t in zip(f.loc[fix, "year"], f.loc[fix, "team"])
        ]

    if laps is not None and len(laps):
        laps = laps.copy()
        lap_blank = laps["team"].fillna("").str.strip() == ""
        if lap_blank.any():
            team_of = f.groupby(["year", "round", "driver"])["team"].agg(lambda x: x.mode().iat[0])
            laps.loc[lap_blank, "team"] = [
                team_of.get((y, r, d), "")
                for y, r, d in zip(laps.loc[lap_blank, "year"], laps.loc[lap_blank, "round"],
                                   laps.loc[lap_blank, "driver"])
            ]
    return f, laps


def extract(session, year: int, round_number: int, session_idx: int):
    """Build (features, laps, stints) for one loaded session."""
    laps, timed, clean = _prepare_laps(session)
    lr = _long_runs(laps, clean)

    drivers = pd.Index(sorted(laps["Driver"].dropna().unique()), name="driver")
    f = pd.DataFrame(index=drivers)

    res = session.results
    res = res.set_index("Abbreviation") if "Abbreviation" in res.columns else pd.DataFrame()

    f["team"] = laps.groupby("Driver")["Team"].agg(lambda x: x.mode().iat[0] if x.notna().any() else "")
    # FastF1 occasionally omits laps.Team for a whole session (seen: 2026 R5 and R7 FP1);
    # fall back to the results table so those rows keep their team and colour.
    if "TeamName" in res.columns:
        blank = f["team"].fillna("").astype(str).str.strip() == ""
        f.loc[blank, "team"] = res["TeamName"].reindex(f.index[blank]).fillna("")
    f["n_laps"] = laps.groupby("Driver").size()
    f["n_clean"] = laps[clean].groupby("Driver").size()
    f["n_clean"] = f["n_clean"].fillna(0).astype(int)

    # Pace on the fastest valid lap; yellow-flag laps allowed here (they are simply slower).
    f["best_lap_s"] = laps[timed].groupby("Driver")["lap_time_s"].min()
    fastest = f["best_lap_s"].min()
    f["gap_to_best_s"] = f["best_lap_s"] - fastest
    f["pace_rank"] = f["best_lap_s"].rank(method="min")
    for k in (1, 2, 3):
        f[f"s{k}_best_s"] = laps[timed].groupby("Driver")[f"s{k}_s"].min()

    # Long-run pace (compound-neutral)
    if len(lr):
        g = lr.groupby("Driver")
        f["longrun_n"] = g.size()
        f["longrun_pace_s"] = g["lap_time_s"].median()
        f["longrun_delta_s"] = g["longrun_delta_s"].median()
        f["deg_slope_s_per_lap"] = _degradation(lr)
        f["longrun_gap_s"] = f["longrun_delta_s"] - f["longrun_delta_s"].min()
        f["longrun_rank"] = f["longrun_delta_s"].rank(method="min")
    else:
        for col in ("longrun_n", "longrun_pace_s", "longrun_delta_s",
                    "deg_slope_s_per_lap", "longrun_gap_s", "longrun_rank"):
            f[col] = np.nan
    f["longrun_n"] = f["longrun_n"].fillna(0).astype(int)

    stints = _stints(laps)
    # most-used dry compound = a cheap "what did they run" summary
    main = (laps[laps["Compound"].isin(DRY_COMPOUNDS)].groupby("Driver")["Compound"]
            .agg(lambda x: x.mode().iat[0]))
    f["main_compound"] = main
    # New soft-tyre sets fitted this session (a stint starting on a fresh soft). Sets used before
    # Sunday are sets the driver no longer has for the race.
    if {"FreshTyre", "Stint"} <= set(laps.columns):
        starts = laps.sort_values("LapNumber").groupby(["Driver", "Stint"]).first()
        fresh_soft = starts[(starts["FreshTyre"] == True) & (starts["Compound"] == "SOFT")]  # noqa: E712
        f["new_soft_sets"] = fresh_soft.groupby(level="Driver").size().reindex(f.index)
    else:
        f["new_soft_sets"] = np.nan
    f["new_soft_sets"] = f["new_soft_sets"].fillna(0).astype(int)

    # Classification / colours from results (may be sparse for practice sessions)
    def _from_res(col, conv=lambda x: x):
        if col in res.columns:
            return conv(res[col]).reindex(f.index)
        return pd.Series(np.nan, index=f.index)
    f["team_color"] = _from_res("TeamColor").map(_team_color)
    f["position"] = _from_res("Position", pd.to_numeric)
    f["grid"] = _from_res("GridPosition", pd.to_numeric)
    f["status"] = _from_res("Status")
    for q in ("Q1", "Q2", "Q3"):
        f[f"{q.lower()}_s"] = _from_res(q, _secs)
    # FastF1 only flags laps deleted by the stewards when race-control messages are loaded, which
    # this pipeline skips; in qualifying ~2.5% of "best laps" were deleted laps. The official Q1-Q3
    # times are authoritative, so use them for the qualifying best lap where they exist.
    official = f[["q1_s", "q2_s", "q3_s"]].min(axis=1)
    if session.name == "Qualifying" and official.notna().any():
        f["best_lap_s"] = official.where(official.notna(), f["best_lap_s"])
        f["gap_to_best_s"] = f["best_lap_s"] - f["best_lap_s"].min()
        f["pace_rank"] = f["best_lap_s"].rank(method="min")

    meta = dict(
        year=year, round=round_number,
        location=str(session.event["Location"]),
        event_name=str(session.event["EventName"]),
        event_date=pd.Timestamp(session.event["EventDate"]).date().isoformat(),
        session=session.name, session_idx=session_idx,
    )
    features = f.reset_index()
    for i, (k, v) in enumerate(meta.items()):
        features.insert(i, k, v)

    keep = laps[clean].copy()
    keep["Team"] = keep["Driver"].map(f["team"])  # use the repaired team, not the raw column
    keep["longrun_delta_s"] = lr["longrun_delta_s"].reindex(keep.index) if len(lr) else np.nan
    lap_tbl = keep.rename(columns={
        "Driver": "driver", "Team": "team", "LapNumber": "lap", "Stint": "stint",
        "Compound": "compound", "TyreLife": "tyre_life",
    })[["driver", "team", "lap", "lap_time_s", "stint", "compound", "tyre_life",
        "s1_s", "s2_s", "s3_s", "longrun_delta_s"]]

    for tbl in (lap_tbl, stints):
        for i, k in enumerate(["year", "round", "session", "session_idx"]):
            tbl.insert(i, k, meta[k])
    return features, lap_tbl.reset_index(drop=True), stints.reset_index(drop=True)
