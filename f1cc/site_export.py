"""Export the stored data as JSON for the web frontend (web/, Next.js on Vercel).

The website never runs the model: it only shows what the pipeline already computed. This module
turns the parquet tables into small JSON files with the same numbers the Streamlit app shows.

Replay integrity: a weekend's replay file holds only what the app may see during the weekend -
practice/qualifying data, the prediction made after each session and commentary built from
those. The race result lives in a *separate* file (``race/<year>-<round>.json``) that the site
fetches only when the viewer asks to reveal it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from f1cc import backtest_summary as bts
from f1cc import commentary, store
from f1cc.predict.base import finished
from f1cc.replay import Cutoff, Weekend, apply_cutoff

SITE_YEAR = 2026
HOLDOUT_FROM = 16                       # docs/evaluation.md section 6: model frozen before this round
FROZEN_TAG = "frozen-2026-r15b"
KIND = {"Practice 1": "practice", "Practice 2": "practice", "Practice 3": "practice",
        "Sprint Qualifying": "sprint_quali", "Sprint": "sprint", "Qualifying": "quali"}
SHORT = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3", "Sprint Qualifying": "Sprint Quali",
         "Sprint": "Sprint", "Qualifying": "Quali", "Race": "Race"}


def _clean(x):
    """JSON-safe: NaN -> None, numpy -> python, floats rounded to 4 places."""
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, np.ndarray)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return None if math.isnan(x) or math.isinf(x) else round(float(x), 4)
    if x is None or x is pd.NaT or x is pd.NA:
        return None
    return x


def _range(p_pos, lo: float = 0.1, hi: float = 0.9) -> tuple[int, int]:
    """Positions between which the driver finishes in 80% of the simulated races."""
    c = np.cumsum(np.asarray(p_pos, dtype=float))
    return int(np.searchsorted(c, lo) + 1), int(min(np.searchsorted(c, hi) + 1, len(c)))


def prediction_rows(pred: pd.DataFrame) -> list[dict]:
    rows = []
    for r in pred.sort_values("expected_pos").itertuples(index=False):
        dist = np.asarray(r.p_pos, dtype=float)
        lo, hi = _range(dist)
        rows.append({"driver": r.driver, "pos": int(r.expected_pos), "sigma": r.sigma, "p_win": r.p_win,
                     "p_podium": r.p_podium, "p_points": float(dist[:10].sum()), "p_dnf": r.p_dnf,
                     "lo": lo, "hi": hi, "dist": [round(float(v), 4) for v in dist]})
    return rows


def _timesheet(rows: pd.DataFrame, session: str) -> list[dict]:
    official = KIND[session] in ("quali", "sprint") and rows["position"].notna().any()
    order = rows.sort_values("position" if official else "pace_rank", na_position="last")
    out = []
    for i, r in enumerate(order.itertuples(index=False), start=1):
        out.append({"driver": r.driver, "pos": int(r.position) if official and pd.notna(r.position) else i,
                    "best": r.best_lap_s, "gap": r.gap_to_best_s, "laps": int(r.n_laps),
                    "status": r.status if session == "Sprint" else None})
    return out


def _longruns(laps: pd.DataFrame) -> list[dict]:
    lr = laps.dropna(subset=["longrun_delta_s"])
    out = []
    for drv, g in lr.groupby("driver"):
        q1, med, q3 = np.percentile(g["longrun_delta_s"], [25, 50, 75])
        out.append({"driver": drv, "n": int(len(g)), "median": med, "q1": q1, "q3": q3})
    return sorted(out, key=lambda d: d["median"])


def _stints(stints: pd.DataFrame) -> list[dict]:
    return [{"driver": r.driver, "compound": r.compound, "start": int(r.lap_start), "end": int(r.lap_end)}
            for r in stints.sort_values(["driver", "stint"]).itertuples(index=False)
            if pd.notna(r.lap_start) and pd.notna(r.lap_end)]


def _drivers(features: pd.DataFrame, names: dict[str, dict]) -> dict[str, dict]:
    """Code -> name/team/colour as of the weekend (teams can change during a season)."""
    latest = features.sort_values("session_idx").groupby("driver").last()
    return {d: {"name": names.get(d, {}).get("name", d), "number": names.get(d, {}).get("number"),
                "team": r.team, "color": r.team_color if isinstance(r.team_color, str) else "#8A8D93"}
            for d, r in latest.iterrows()}


def auto_choice(bt: pd.DataFrame, round_number: int, stage: int) -> str:
    return bts.pick(bt, round_number, stage)


def build_weekend(tables: dict[str, pd.DataFrame], preds: pd.DataFrame, bt: pd.DataFrame,
                  year: int, round_number: int, names: dict[str, dict], live: bool,
                  session_starts: dict[str, str | None]) -> dict:
    features, laps, stints = tables["features"], tables["laps"], tables["stints"]
    weekend = Weekend.from_features(features, year, round_number)
    short_names = {k: v["name"] for k, v in names.items()}
    wk_f = features[(features["year"] == year) & (features["round"] == round_number)
                    & (features["session"] != "Race")]
    steps, prev = [], None
    for k, session in enumerate(weekend.replayable, start=1):
        cut = Cutoff(weekend, k)
        f, lp, st = (apply_cutoff(t, cut) for t in (features, laps, stints))
        rows = f[f["session"] == session]
        chosen = auto_choice(bt, round_number, k)
        mine = preds[(preds["round"] == round_number) & (preds["stage"] == k)]
        by = {p: prediction_rows(g) for p, g in mine.groupby("predictor")}
        now = mine[mine["predictor"] == chosen]
        notes = commentary.session_notes(session, rows, short_names)
        if session == "Qualifying":
            rec = commentary.pole_record(features, year, round_number)
            notes += [rec] if rec else []
        if len(now):
            notes += commentary.prediction_notes(now, prev, short_names)
        prev = now if len(now) else prev
        # The official grid only exists once the race has run (FastF1 publishes it with the
        # result) or once someone hand-enters it from published grids. In between - the live
        # weekend - fall back to qualifying order and say so, rather than show nothing.
        grid, grid_state = pd.DataFrame(), None
        if session == "Qualifying":
            grid = store.starting_grid(features, year, round_number)
            if len(grid):
                grid_state = "official"
            elif rows["position"].notna().any():
                grid = (rows.dropna(subset=["position"]).sort_values("position")
                        .assign(grid=lambda d: range(1, len(d) + 1), penalty=np.nan)[["driver", "grid", "penalty"]])
                grid_state = "provisional"
        steps.append({
            "session": session, "short": SHORT[session], "kind": KIND[session], "stage": k,
            "start_utc": session_starts.get(session),
            "timesheet": _timesheet(rows, session),
            "longrun": _longruns(lp[lp["session"] == session]) if KIND[session] == "practice" else [],
            "stints": _stints(st[st["session"] == session]),
            "grid_state": grid_state,
            "grid": [{"driver": r.driver, "grid": None if pd.isna(r.grid) else int(r.grid),
                      "penalty": None if pd.isna(r.penalty) else str(r.penalty)}
                     for r in grid.itertuples(index=False)],
            "prediction": {"auto": chosen, "by": by},
            "commentary": notes,
        })
    return _clean({"year": year, "round": round_number, "name": weekend.event_name,
                   "location": weekend.location, "date": weekend.event_date, "live": live,
                   "format": "sprint" if "Sprint" in weekend.sessions else "conventional",
                   "race_start_utc": session_starts.get("Race"),
                   "drivers": _drivers(wk_f, names), "steps": steps})


def build_race(features: pd.DataFrame, preds: pd.DataFrame, bt: pd.DataFrame, year: int,
               round_number: int, names: dict[str, dict]) -> dict | None:
    race = features[(features["year"] == year) & (features["round"] == round_number)
                    & (features["session"] == "Race")]
    if race.empty or race["position"].isna().all():
        return None
    race = race.sort_values("position")
    result = [{"driver": r.driver, "pos": int(r.position), "grid": None if pd.isna(r.grid) or r.grid == 0 else int(r.grid),
               "status": r.status, "finished": bool(finished(pd.Series([r.status or ""])).iloc[0])}
              for r in race.itertuples(index=False)]
    scores = bt[bt["round"] == round_number]
    full = bts.with_auto(bt)
    auto_rows = full[(full["round"] == round_number) & (full["predictor"] == bts.AUTO)]
    by_stage = {}
    for k, g in pd.concat([scores, auto_rows]).groupby("stage"):
        by_stage[int(k)] = {r.predictor: {"spearman": r.spearman, "winner_hit": r.winner_hit,
                                          "podium_hits": round(r.top3_overlap * 3), "mae": r.mae_pos}
                            for r in g.itertuples(index=False)}
    last = int(preds[preds["round"] == round_number]["stage"].max())
    chosen = auto_choice(bt, round_number, last)
    p = preds[(preds["round"] == round_number) & (preds["stage"] == last) & (preds["predictor"] == chosen)]
    df = p.merge(race[["driver", "position", "grid", "status"]], on="driver").rename(columns={"position": "actual"})
    notes = commentary.race_notes(df, {k: v["name"] for k, v in names.items()}) if len(df) else []
    return _clean({"year": year, "round": round_number, "result": result, "scores": by_stage,
                   "auto": {int(k): auto_choice(bt, round_number, int(k)) for k in by_stage},
                   "commentary": notes})


def build_accuracy(bt: pd.DataFrame) -> dict:
    full = bts.with_auto(bt)
    summary = full.groupby(["stage", "predictor"]).agg(
        spearman=("spearman", "mean"), winner_hit=("winner_hit", "mean"),
        podium_hits=("top3_overlap", lambda s: s.mean() * 3), mae=("mae_pos", "mean"),
        races=("round", "nunique")).reset_index()
    per_round = full[["round", "stage", "predictor", "spearman", "winner_hit", "top3_overlap", "mae_pos"]]
    return _clean({"year": SITE_YEAR, "holdout_from": HOLDOUT_FROM, "frozen_tag": FROZEN_TAG,
                   "baseline": bts.BASELINE, "auto": bts.AUTO,
                   "summary": summary.to_dict(orient="records"),
                   "per_round": [{"round": int(r.round), "stage": int(r.stage), "predictor": r.predictor,
                                  "spearman": r.spearman, "winner_hit": r.winner_hit,
                                  "podium_hits": r.top3_overlap * 3, "mae": r.mae_pos}
                                 for r in per_round.itertuples(index=False)]})


def build_season(features: pd.DataFrame, preds: pd.DataFrame, bt: pd.DataFrame,
                 schedule: pd.DataFrame, names: dict[str, dict]) -> dict:
    f = features[features["year"] == SITE_YEAR]
    stored = set(f["round"])
    raced = set(f.loc[(f["session"] == "Race") & f["position"].notna(), "round"])
    rounds = []
    for r in schedule.sort_values("round").itertuples(index=False):
        rd = int(r.round)
        status = "finished" if rd in raced else "live" if rd in stored else "upcoming"
        item = {"round": rd, "name": r.name, "location": r.location, "country": r.country,
                "format": r.format, "sessions": json.loads(r.sessions), "status": status}
        if status == "finished":
            race = f[(f["round"] == rd) & (f["session"] == "Race")].dropna(subset=["position"])
            item["winner"] = race.loc[race["position"].idxmin(), "driver"]
        if status in ("finished", "live"):
            last = int(preds[preds["round"] == rd]["stage"].max()) if (preds["round"] == rd).any() else None
            if last:
                chosen = auto_choice(bt, rd, last)
                p = preds[(preds["round"] == rd) & (preds["stage"] == last) & (preds["predictor"] == chosen)]
                fav = p.loc[p["expected_pos"].idxmin()]
                item["favourite"] = {"driver": fav["driver"], "p_win": fav["p_win"]}
        rounds.append(item)
    return _clean({"year": SITE_YEAR, "rounds": rounds,
                   "drivers": _drivers(f[f["session"] != "Race"], names)})


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))


def export(out_dir: Path, schedule: pd.DataFrame, names: dict[str, dict]) -> list[Path]:
    """Write every site file under ``out_dir`` (web/). Returns the paths written."""
    tables = {t: store.read(t, [SITE_YEAR]) for t in store.TABLES}
    preds, bt = store.read("predictions", [SITE_YEAR]), store.read("backtest", [SITE_YEAR])
    f = tables["features"]
    season = build_season(f, preds, bt, schedule, names)
    written = [out_dir / "data" / "season.json", out_dir / "data" / "accuracy.json"]
    write_json(written[0], season)
    write_json(written[1], build_accuracy(bt))
    starts = {int(r.round): {s["name"]: s["start_utc"] for s in json.loads(r.sessions)}
              for r in schedule.itertuples(index=False)}
    for item in season["rounds"]:
        rd = item["round"]
        if item["status"] == "upcoming":
            continue
        wk = build_weekend(tables, preds, bt, SITE_YEAR, rd, names, item["status"] == "live", starts.get(rd, {}))
        p = out_dir / "data" / "weekends" / f"{SITE_YEAR}-{rd:02d}.json"
        write_json(p, wk)
        written.append(p)
        race = build_race(f, preds, bt, SITE_YEAR, rd, names)
        if race:
            p = out_dir / "public" / "data" / "race" / f"{SITE_YEAR}-{rd:02d}.json"
            write_json(p, race)
            written.append(p)
    return written
