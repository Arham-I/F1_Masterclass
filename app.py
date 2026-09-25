"""F1 Race Weekend Companion - Streamlit front end.

Presentation only. All logic lives in ``f1cc/``; this file wires replay state to charts.
The app reads derived parquet from data/ and never imports FastF1, so it deploys as-is.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from f1cc import backtest_summary as bts
from f1cc import charts, store
from f1cc.predict.base import finished
from f1cc.replay import Cutoff, Weekend, apply_cutoff

st.set_page_config(page_title="F1 Race Weekend Companion", page_icon="🏁", layout="wide")


@st.cache_data(show_spinner=False)
def load_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return store.read("features"), store.read("laps"), store.read("stints")


@st.cache_data(show_spinner=False)
def load_predictions(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    return store.read("predictions", [year]), store.read("backtest", [year])


@st.cache_data(show_spinner=False)
def list_weekends(features: pd.DataFrame) -> tuple[list[tuple[int, int]], set[tuple[int, int]]]:
    """All weekends newest first, and the set of *live* ones (sessions stored, race not run yet)."""
    all_ = set(map(tuple, features[["year", "round"]].drop_duplicates().to_numpy().tolist()))
    raced = set(map(tuple, features.loc[features["session"] == "Race", ["year", "round"]]
                    .drop_duplicates().to_numpy().tolist()))
    return sorted(all_, reverse=True), all_ - raced


def stepper_html(cutoff: Cutoff) -> str:
    """One pill per replayable session: revealed / current / upcoming."""
    pills = []
    for i, name in enumerate(cutoff.weekend.replayable):
        state = "done" if i < cutoff.revealed - 1 else "now" if i == cutoff.revealed - 1 else "next"
        pills.append(f"<span class='pill {state}'>{name}</span>")
    return "<div class='stepper'>" + "".join(pills) + "</div>"


STYLE = """
<style>
.stepper{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 2px}
.pill{padding:4px 12px;border-radius:999px;font-size:13px;border:1px solid #2C2C2A;color:#6F6F6B}
.pill.done{color:#A8A8A3;border-color:#3A3A37}
.pill.now{color:#fff;background:#E10600;border-color:#E10600;font-weight:600}
</style>
"""


STAGE_LABELS = {1: "1st session", 2: "2nd session", 3: "3rd session", 4: "Qualifying"}


PCT = st.column_config.NumberColumn(format="%.2f%%")


def auto_or(bt: pd.DataFrame, who: str, round_number: int, stage: int) -> str:
    return bts.pick(bt, round_number, stage) if who == bts.AUTO else who


def predictor_choice(preds: pd.DataFrame, key: str) -> str:
    return st.selectbox("Predictor", [bts.AUTO, *dict.fromkeys(preds["predictor"])], index=0, key=key,
                        help="Auto uses, at each stage, whichever predictor has the best record on this "
                             "season's earlier races (the baseline until 3 races exist). It only looks at "
                             "finished races, so it never sees the answer.")


def session_result(f: pd.DataFrame, session: str) -> pd.DataFrame:
    """The session's own classification: official position for Qualifying / Sprint, else pace rank."""
    pos = f["position"] if session in ("Qualifying", "Sprint") and f["position"].notna().any() else f["pace_rank"]
    return pd.DataFrame({"driver": f["driver"].to_numpy(), "session_pos": pos.to_numpy(),
                         "session_gap": f["gap_to_best_s"].to_numpy()})


def prediction_section(cutoff: Cutoff, stage: int, session_f: pd.DataFrame, session: str) -> None:
    """Race prediction made right after ``session`` (stage ``stage``), side by side with that
    session's result. Predictions are precomputed per stage by scripts/backtest.py, so the one
    shown here was built without any later session."""
    st.subheader("Race prediction")
    preds, bt = load_predictions(cutoff.weekend.year)
    if preds.empty:
        st.info("Predictions exist for 2026 only.")
        return
    who = predictor_choice(preds, "predictor_replay")
    w = cutoff.weekend
    labels = {i + 1: n for i, n in enumerate(w.replayable)}
    source = {k: auto_or(bt, who, w.round, k) for k in labels}
    mine = pd.concat([preds[(preds["round"] == w.round) & (preds["stage"] == k) & (preds["predictor"] == p)]
                      for k, p in source.items()])
    now = mine[mine["stage"] == stage]
    shown = f"Auto → {source[stage]}" if who == bts.AUTO else who
    left, right = st.columns([3, 2])
    left.plotly_chart(charts.prediction_chart(now, labels[stage], shown), width="stretch",
                      config={"displayModeBar": False})
    right.plotly_chart(charts.uncertainty_chart(mine, labels, stage), width="stretch",
                       config={"displayModeBar": False})
    if stage < len(w.replayable) or "Qualifying" not in w.replayable[:stage]:
        st.caption("Before Qualifying there is no grid, so the prediction has to guess qualifying "
                   "too: expect wide error bars that tighten as the weekend goes on.")

    st.markdown(f"**Prediction after {session} vs the {session} result** · whole grid")
    table = (now[["expected_pos", "driver", "team", "p_win", "p_podium", "p_dnf"]]
             .merge(session_result(session_f, session), on="driver", how="left")
             .sort_values("expected_pos"))
    for c in ("p_win", "p_podium", "p_dnf"):
        table[c] = table[c] * 100
    st.dataframe(table[["expected_pos", "driver", "team", "session_pos", "session_gap", "p_win", "p_podium", "p_dnf"]],
                 hide_index=True, width="stretch", height=35 * (len(table) + 1) + 3,
                 column_config={"expected_pos": st.column_config.NumberColumn("Predicted finish", format="P%d"),
                                "driver": "Driver", "team": "Team",
                                "session_pos": st.column_config.NumberColumn(f"{session} position", format="P%d"),
                                "session_gap": st.column_config.NumberColumn(f"{session} gap (s)", format="+%.3f"),
                                "p_win": st.column_config.NumberColumn("Win", format="%.2f%%"),
                                "p_podium": st.column_config.NumberColumn("Podium", format="%.2f%%"),
                                "p_dnf": st.column_config.NumberColumn("Retirement", format="%.2f%%")})

    with st.expander("Backtest: how good is this, really?"):
        full = bts.with_auto(bt)
        summary = bts.summarize(full)
        st.plotly_chart(charts.backtest_chart(summary, STAGE_LABELS), width="stretch",
                        config={"displayModeBar": False})
        st.plotly_chart(charts.trend_chart(bts.season_trend(full, stage), labels[stage],
                                           upto_round=w.round), width="stretch", config={"displayModeBar": False})
        for name in (bts.AUTO, "Ridge (all seasons)"):
            diff = bts.paired_diff(full, name)
            st.caption(f"{name} minus baseline (Spearman), 95% interval over the races: "
                       + " · ".join(f"{STAGE_LABELS[int(r.stage)]} {r['diff']:+.3f} [{r.lo:+.3f}, {r.hi:+.3f}]"
                                    for _, r in diff.iterrows()))
        after_q = summary[summary["stage"] == 4].set_index("predictor")
        st.caption("How good are the percentages? Winner log-loss after Qualifying (lower = better; "
                   "a uniform guess over 22 cars scores 3.09): "
                   + " · ".join(f"{p} {v:.2f}" for p, v in after_q["winner_logloss"].items()))


def race_view(features: pd.DataFrame, weekend: Weekend) -> None:
    """Show-only page: the real race result next to what was predicted. Reads the stored
    predictions and the Race classification; nothing here feeds back into any prediction."""
    st.title(f"{weekend.event_name} · race result")
    st.caption(f"{weekend.year} · Round {weekend.round} · {weekend.location} · {weekend.event_date}")
    preds, bt = load_predictions(weekend.year)
    mine_all = preds[preds["round"] == weekend.round] if not preds.empty else preds
    if mine_all.empty:
        st.info("No stored predictions for this weekend (predictions exist for 2026 only).")
        return
    labels = {i + 1: n for i, n in enumerate(weekend.replayable)}
    c1, c2 = st.columns([2, 3])
    stage = c1.select_slider("Prediction made after", options=list(labels), value=max(labels),
                             format_func=lambda k: labels[k])
    with c2:
        who = predictor_choice(preds, "predictor_race")
    source = auto_or(bt, who, weekend.round, stage)
    shown = f"Auto → {source}" if who == bts.AUTO else who
    pred = mine_all[(mine_all["stage"] == stage) & (mine_all["predictor"] == source)]
    race = features[(features["year"] == weekend.year) & (features["round"] == weekend.round)
                    & (features["session"] == "Race")][["driver", "position", "grid", "status"]]
    df = pred.merge(race, on="driver", how="inner").rename(columns={"position": "actual"})
    df["finished"] = finished(df["status"].fillna(""))
    df["delta"] = df["expected_pos"] - df["actual"]

    winner = df.loc[df["actual"].idxmin()]
    top3_pred, top3_real = set(df.nsmallest(3, "expected_pos")["driver"]), set(df.nsmallest(3, "actual")["driver"])
    m = st.columns(4)
    m[0].metric("Winner", winner["driver"], f"given {winner['p_win']:.2%} to win", delta_color="off")
    m[1].metric("Podium picked", f"{len(top3_pred & top3_real)} of 3", ", ".join(sorted(top3_real)), delta_color="off")
    m[2].metric("Order agreement (Spearman)", f"{df['expected_pos'].rank().corr(df['actual'].rank()):.3f}")
    m[3].metric("Typical miss", f"{(df['expected_pos'] - df['actual']).abs().mean():.1f} places")

    st.plotly_chart(charts.result_vs_prediction_chart(df, labels[stage], shown), width="stretch",
                    config={"displayModeBar": False})
    table = df.sort_values("actual")[["actual", "driver", "team", "expected_pos", "delta", "p_win",
                                      "p_podium", "p_dnf", "status"]].copy()
    for c in ("p_win", "p_podium", "p_dnf"):
        table[c] = table[c] * 100
    st.dataframe(table, hide_index=True, width="stretch", height=35 * (len(table) + 1) + 3,
                 column_config={"actual": st.column_config.NumberColumn("Finished", format="P%d"),
                                "driver": "Driver", "team": "Team",
                                "expected_pos": st.column_config.NumberColumn("Predicted", format="P%d"),
                                "delta": st.column_config.NumberColumn("vs predicted", format="%+d",
                                                                       help="+ = finished ahead of the prediction"),
                                "p_win": st.column_config.NumberColumn("Win %", format="%.2f%%"),
                                "p_podium": st.column_config.NumberColumn("Podium %", format="%.2f%%"),
                                "p_dnf": st.column_config.NumberColumn("Retire %", format="%.2f%%"),
                                "status": "Status"})
    st.caption("This page only displays the result next to the stored predictions. The replay view never "
               "sees race data, and nothing here changes how any prediction is made.")


def main() -> None:
    st.markdown(STYLE, unsafe_allow_html=True)
    features, laps, stints = load_tables()
    if features.empty:
        st.error("No data found in data/. Run `python scripts/backfill.py --years 2026` first.")
        st.stop()

    weekends, live = list_weekends(features)
    with st.sidebar:
        st.header("Replay")
        labels = {yr_rd: Weekend.from_features(features, *yr_rd).label() for yr_rd in weekends}
        default = next(i for i, k in enumerate(weekends) if k not in live)   # latest finished weekend
        choice = st.selectbox("Weekend", weekends, index=default,
                              format_func=lambda k: f"{'🔴 LIVE · ' if k in live else ''}{k[0]} · {labels[k]}")
        st.caption("Replays a finished weekend session by session. "
                   "Nothing after the current session is visible to the app.")
        view = st.radio("View", ["Replay weekend", "Race result"], disabled=choice in live,
                        help="Race result shows the real finishing order next to the prediction. "
                             "Not available for a live weekend: the race has not been run.")

    weekend = Weekend.from_features(features, *choice)
    if view == "Race result" and choice not in live:
        race_view(features, weekend)
        return
    key = f"revealed_{choice[0]}_{choice[1]}"
    st.session_state.setdefault(key, 0)
    cutoff = Cutoff(weekend, st.session_state[key])

    st.title(f"{weekend.event_name}")
    st.caption(f"{weekend.year} · Round {weekend.round} · {weekend.location} · {weekend.event_date}")
    st.markdown(stepper_html(cutoff), unsafe_allow_html=True)
    if choice in live:
        st.warning(f"**Live weekend.** The race has not been run yet: sessions so far are "
                   f"{', '.join(weekend.replayable)}. The prediction below is a real forecast, not a replay.")

    c1, c2, _ = st.columns([1, 1, 6])
    if c1.button("▶ Next session", disabled=cutoff.is_done, type="primary", width="stretch"):
        st.session_state[key] = cutoff.advance().revealed
        st.rerun()
    if c2.button("↺ Reset", disabled=cutoff.revealed == 0, width="stretch"):
        st.session_state[key] = 0
        st.rerun()

    if cutoff.revealed == 0:
        st.info(f"Nothing has happened yet. Press **Next session** to run {cutoff.next_session}.")
        return

    # Everything below sees only data allowed by the cutoff.
    vis_f, vis_l, vis_s = (apply_cutoff(t, cutoff) for t in (features, laps, stints))
    session = st.radio("Session", cutoff.visible, index=len(cutoff.visible) - 1, horizontal=True)
    f = vis_f[vis_f["session"] == session]
    l = vis_l[vis_l["session"] == session]
    s = vis_s[vis_s["session"] == session]

    left, right = st.columns(2)
    left.plotly_chart(charts.pace_gap_chart(f, session), width="stretch",
                      config={"displayModeBar": False})
    right.plotly_chart(charts.longrun_chart(f, l, session), width="stretch",
                       config={"displayModeBar": False})
    st.plotly_chart(charts.stint_chart(f, s, session), width="stretch",
                    config={"displayModeBar": False})

    prediction_section(cutoff, cutoff.visible.index(session) + 1, f, session)

    with st.expander("Table view"):
        cols = ["driver", "team", "best_lap_s", "gap_to_best_s", "pace_rank", "longrun_n",
                "longrun_delta_s", "deg_slope_s_per_lap", "main_compound"]
        st.dataframe(f.sort_values("pace_rank")[cols], hide_index=True, width="stretch")


main()
