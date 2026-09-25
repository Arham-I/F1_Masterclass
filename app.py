"""F1 Race Weekend Companion - Streamlit front end.

Presentation only. All logic lives in ``f1cc/``; this file wires replay state to charts.
The app reads derived parquet from data/ and never imports FastF1, so it deploys as-is.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from f1cc import backtest_summary as bts
from f1cc import charts, store
from f1cc.replay import Cutoff, Weekend, apply_cutoff

st.set_page_config(page_title="F1 Race Weekend Companion", page_icon="🏁", layout="wide")


@st.cache_data(show_spinner=False)
def load_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return store.read("features"), store.read("laps"), store.read("stints")


@st.cache_data(show_spinner=False)
def load_predictions(year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    return store.read("predictions", [year]), store.read("backtest", [year])


@st.cache_data(show_spinner=False)
def list_weekends(features: pd.DataFrame) -> list[tuple[int, int]]:
    """(year, round) pairs that have a Race session, newest first: complete, replayable weekends."""
    done = features[features["session"] == "Race"][["year", "round"]].drop_duplicates()
    return sorted(map(tuple, done.to_numpy().tolist()), reverse=True)


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


def prediction_section(cutoff: Cutoff) -> None:
    """Race prediction as of the revealed sessions. Predictions are precomputed by
    scripts/backtest.py *per stage*, so the row shown here was built without later sessions."""
    st.subheader("Race prediction")
    preds, bt = load_predictions(cutoff.weekend.year)
    if preds.empty:
        st.info("Predictions exist for 2026 only.")
        return
    names = [bts.AUTO, *dict.fromkeys(preds["predictor"])]
    who = st.selectbox("Predictor", names, index=0, help="Auto uses, at each stage, whichever predictor "
                       "has the best record on this season's earlier races (the baseline until 3 races "
                       "exist). It only looks at finished races, so it never sees the answer.")
    w = cutoff.weekend
    labels = {i + 1: n for i, n in enumerate(w.replayable)}
    source = {k: bts.pick(bt, w.round, k) if who == bts.AUTO else who for k in labels}
    mine = pd.concat([preds[(preds["round"] == w.round) & (preds["stage"] == k) & (preds["predictor"] == p)]
                      for k, p in source.items()])
    now = mine[mine["stage"] == cutoff.revealed]
    shown = f"Auto → {source[cutoff.revealed]}" if who == bts.AUTO else who
    left, right = st.columns([3, 2])
    left.plotly_chart(charts.prediction_chart(now, labels[cutoff.revealed], shown), width="stretch",
                      config={"displayModeBar": False})
    right.plotly_chart(charts.uncertainty_chart(mine, labels, cutoff.revealed), width="stretch",
                       config={"displayModeBar": False})
    if cutoff.revealed < 4:
        st.caption("Before Qualifying there is no grid, so the prediction has to guess qualifying "
                   "too: expect wide error bars that tighten as the weekend goes on.")
    with st.expander("Backtest: how good is this, really?"):
        full = bts.with_auto(bt)
        summary = bts.summarize(full)
        st.plotly_chart(charts.backtest_chart(summary, STAGE_LABELS), width="stretch",
                        config={"displayModeBar": False})
        st.plotly_chart(charts.trend_chart(bts.season_trend(full, cutoff.revealed), labels[cutoff.revealed],
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


def main() -> None:
    st.markdown(STYLE, unsafe_allow_html=True)
    features, laps, stints = load_tables()
    if features.empty:
        st.error("No data found in data/. Run `python scripts/backfill.py --years 2026` first.")
        st.stop()

    weekends = list_weekends(features)
    with st.sidebar:
        st.header("Replay")
        labels = {yr_rd: Weekend.from_features(features, *yr_rd).label() for yr_rd in weekends}
        choice = st.selectbox("Weekend", weekends, format_func=lambda k: f"{k[0]} · {labels[k]}")
        st.caption("Replays a finished weekend session by session. "
                   "Nothing after the current session is visible to the app.")

    weekend = Weekend.from_features(features, *choice)
    key = f"revealed_{choice[0]}_{choice[1]}"
    st.session_state.setdefault(key, 0)
    cutoff = Cutoff(weekend, st.session_state[key])

    st.title(f"{weekend.event_name}")
    st.caption(f"{weekend.year} · Round {weekend.round} · {weekend.location} · {weekend.event_date}")
    st.markdown(stepper_html(cutoff), unsafe_allow_html=True)

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

    prediction_section(cutoff)

    with st.expander("Table view"):
        cols = ["driver", "team", "best_lap_s", "gap_to_best_s", "pace_rank", "longrun_n",
                "longrun_delta_s", "deg_slope_s_per_lap", "main_compound"]
        st.dataframe(f.sort_values("pace_rank")[cols], hide_index=True, width="stretch")


main()
