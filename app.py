"""F1 Race Weekend Companion - Streamlit front end.

Presentation only. All logic lives in ``f1cc/``; this file wires replay state to charts.
The app reads derived parquet from data/ and never imports FastF1, so it deploys as-is.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from f1cc import charts, store
from f1cc.replay import Cutoff, Weekend, apply_cutoff

st.set_page_config(page_title="F1 Race Weekend Companion", page_icon="🏁", layout="wide")


@st.cache_data(show_spinner=False)
def load_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    return store.read("features"), store.read("laps"), store.read("stints")


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

    with st.expander("Table view"):
        cols = ["driver", "team", "best_lap_s", "gap_to_best_s", "pace_rank", "longrun_n",
                "longrun_delta_s", "deg_slope_s_per_lap", "main_compound"]
        st.dataframe(f.sort_values("pace_rank")[cols], hide_index=True, width="stretch")


main()
