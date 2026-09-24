"""Plotly figures. Pure functions: DataFrames in, ``go.Figure`` out.

Rules (kept deliberately so a React frontend can reuse these unchanged later):
  * never import or call streamlit here
  * one shared theme, applied by ``_style``
  * team colour is a *redundant* channel: every mark is also labelled with its driver code,
    and the hover names driver + team, so identity never depends on colour alone. (Several
    2026 team colours are genuinely close - Williams / Red Bull blues, Cadillac / Haas
    greys, Audi / Ferrari reds - so colour alone would be unreliable.)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

# --- tokens ------------------------------------------------------------------------------
SURFACE = "#1A1A19"
INK = "#ECECEA"        # primary text
INK_2 = "#A8A8A3"      # secondary text
INK_3 = "#6F6F6B"      # muted text
GRID = "#2C2C2A"
ACCENT = "#E10600"
FONT = "Inter, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FALLBACK = "#8A8D93"

# Tyre compounds are semantic categories with a universal F1 colour code.
COMPOUND_COLORS = {
    "SOFT": "#E8383D",
    "MEDIUM": "#FFD12E",
    "HARD": "#EDEDED",
    "INTERMEDIATE": "#43B02A",
    "WET": "#3B8ED0",
    "UNKNOWN": "#6F6F6B",
}
COMPOUND_ORDER = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET", "UNKNOWN"]

ROW_PX = 28            # slot height per driver; bars are capped well under this
MAX_BAR_PX = 22


def fmt_lap(seconds: float) -> str:
    if seconds is None or pd.isna(seconds):
        return "–"
    m, s = divmod(float(seconds), 60)
    return f"{int(m)}:{s:06.3f}"


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def _driver_colors(features: pd.DataFrame) -> dict[str, str]:
    return dict(zip(features["driver"], features["team_color"].fillna(FALLBACK)))


def _driver_teams(features: pd.DataFrame) -> dict[str, str]:
    return dict(zip(features["driver"], features["team"].fillna("")))


def _style(fig: go.Figure, title: str, subtitle: str, n_rows: int, *, legend: bool = False) -> go.Figure:
    height = max(220, n_rows * ROW_PX + 130)
    fig.update_layout(
        title=dict(
            text=(f"<b>{title}</b><br><span style='font-size:12px;font-weight:400;"
                  f"color:{INK_2}'>{subtitle}</span>"),
            x=0, xanchor="left", font=dict(size=16, color=INK),
        ),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_2, size=12),
        height=height,
        margin=dict(l=8, r=24, t=72, b=44),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1,
                    font=dict(color=INK_2, size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor="#262624", bordercolor=GRID, font=dict(color=INK, family=FONT)),
        bargap=max(0.2, 1 - MAX_BAR_PX / ROW_PX),
    )
    fig.update_xaxes(gridcolor=GRID, gridwidth=1, zeroline=False, showline=False,
                     tickfont=dict(color=INK_3), title_font=dict(color=INK_2, size=12))
    fig.update_yaxes(showgrid=False, zeroline=False, showline=False,
                     tickfont=dict(color=INK, size=12), autorange="reversed")
    return fig


def empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(color=INK_2, size=14))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, title, "", 4).update_yaxes(autorange=True)


# --- 1. gap to fastest lap ---------------------------------------------------------------
def pace_gap_chart(features: pd.DataFrame, session: str) -> go.Figure:
    """Best lap of the session, as a gap to the fastest driver (bars grow from the leader)."""
    title = "Gap to fastest lap"
    df = features.dropna(subset=["gap_to_best_s"]).sort_values("gap_to_best_s")
    if df.empty:
        return empty_figure(title, "No timed laps yet")

    fig = go.Figure(go.Bar(
        y=df["driver"], x=df["gap_to_best_s"], orientation="h",
        marker=dict(color=[c if isinstance(c, str) else FALLBACK for c in df["team_color"]],
                    cornerradius=4, line=dict(color=SURFACE, width=2)),
        text=[("P1 " + fmt_lap(b)) if g == 0 else f"+{g:.3f}"
              for b, g in zip(df["best_lap_s"], df["gap_to_best_s"])],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=11),
        customdata=np.stack([df["team"].fillna(""), df["best_lap_s"].map(fmt_lap),
                             df["n_laps"]], axis=-1),
        hovertemplate=("<b>%{y}</b> · %{customdata[0]}<br>Best lap %{customdata[1]}"
                       "<br>Gap +%{x:.3f}s<br>%{customdata[2]} laps<extra></extra>"),
    ))
    fig = _style(fig, title, f"{session} · fastest valid lap per driver", len(df))
    fig.update_xaxes(title="seconds behind the fastest lap", rangemode="tozero")
    return fig


# --- 2. long-run pace distribution -------------------------------------------------------
def longrun_chart(features: pd.DataFrame, laps: pd.DataFrame, session: str) -> go.Figure:
    """Spread of long-run lap times per driver, compound-neutral (lower = faster)."""
    title = "Long-run pace"
    lr = laps.dropna(subset=["longrun_delta_s"])
    if lr.empty:
        return empty_figure(title, "No long runs in this session<br>(needs 5+ clean laps on a stint)")

    colors, teams = _driver_colors(features), _driver_teams(features)
    med = lr.groupby("driver")["longrun_delta_s"].median().sort_values()
    counts = lr.groupby("driver").size()

    fig = go.Figure()
    for drv in med.index:
        c = colors.get(drv, FALLBACK)
        g = lr[lr["driver"] == drv]
        fig.add_trace(go.Box(
            x=g["longrun_delta_s"], y=[drv] * len(g), orientation="h", name=drv,
            marker=dict(color=c, size=4), line=dict(color=c, width=1.5),
            fillcolor=_rgba(c, 0.30), boxpoints=False, showlegend=False,
            hovertemplate=(f"<b>{drv}</b> · {teams.get(drv, '')}<br>"
                           f"{int(counts[drv])} long-run laps<br>"
                           "%{x:+.2f}s vs field (same compound)<extra></extra>"),
        ))
    fig = _style(fig, title, f"{session} · lap time vs field median on the same compound", len(med))
    fig.update_yaxes(categoryorder="array", categoryarray=list(med.index))
    fig.update_xaxes(title="seconds per lap vs field · lower is faster", zeroline=True,
                     zerolinecolor=GRID)
    return fig


# --- 3. tyre stints ----------------------------------------------------------------------
def stint_chart(features: pd.DataFrame, stints: pd.DataFrame, session: str) -> go.Figure:
    """Every stint per driver as coloured segments along the lap axis."""
    title = "Tyre stints"
    if stints.empty:
        return empty_figure(title, "No stint data yet")

    order = (features.sort_values("pace_rank")["driver"].tolist()
             if "pace_rank" in features else sorted(stints["driver"].unique()))
    order = [d for d in order if d in set(stints["driver"])]
    teams = _driver_teams(features)

    fig = go.Figure()
    present = [c for c in COMPOUND_ORDER if c in set(stints["compound"])]
    for comp in present:
        s = stints[stints["compound"] == comp]
        fig.add_trace(go.Bar(
            y=s["driver"], x=s["n_laps"], base=s["lap_start"] - 1, orientation="h", name=comp.title(),
            marker=dict(color=COMPOUND_COLORS.get(comp, FALLBACK), cornerradius=3,
                        line=dict(color=SURFACE, width=2)),
            customdata=np.stack([s["stint"], s["lap_start"], s["lap_end"],
                                 s["driver"].map(lambda d: teams.get(d, ""))], axis=-1),
            hovertemplate=("<b>%{y}</b> · %{customdata[3]}<br>Stint %{customdata[0]} · " + comp.title() +
                           "<br>Laps %{customdata[1]}–%{customdata[2]} (%{x} laps)<extra></extra>"),
        ))
    fig = _style(fig, title, f"{session} · stints by compound, drivers ordered by pace", len(order),
                 legend=len(present) > 1)
    fig.update_layout(barmode="overlay")
    fig.update_yaxes(categoryorder="array", categoryarray=order)
    fig.update_xaxes(title="lap number", rangemode="tozero")
    return fig


# --- 4. race prediction ------------------------------------------------------------------
def prediction_chart(pred: pd.DataFrame, stage_label: str, predictor: str) -> go.Figure:
    """Podium probability per driver (bar) with win probability (marker), best first."""
    title = "Predicted race result"
    if pred.empty:
        return empty_figure(title, "No prediction for this weekend")
    df = pred.sort_values("p_podium", ascending=False).head(12)
    sigma = float(df["sigma"].iloc[0])
    fig = go.Figure(go.Bar(
        y=df["driver"], x=df["p_podium"] * 100, orientation="h",
        marker=dict(color=[c if isinstance(c, str) else FALLBACK for c in df["team_color"]],
                    cornerradius=4, line=dict(color=SURFACE, width=2)),
        text=[f"{p:.0%} podium · {w:.0%} win" for p, w in zip(df["p_podium"], df["p_win"])],
        textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=11),
        customdata=np.stack([df["team"].fillna(""), df["expected_pos"]], axis=-1),
        hovertemplate=("<b>%{y}</b> · %{customdata[0]}<br>Expected finish P%{customdata[1]}"
                       "<br>Podium %{x:.0f}%<extra></extra>"),
    ))
    fig = _style(fig, title, f"{predictor} · after {stage_label} · typical error ±{sigma:.1f} places", len(df))
    fig.update_xaxes(title="podium probability (%)", range=[0, 118])
    return fig


def uncertainty_chart(preds: pd.DataFrame, stage_labels: dict[int, str], current_stage: int) -> go.Figure:
    """How the typical error (sigma, in finishing places) shrinks as sessions are revealed.
    Only stages up to ``current_stage`` are drawn, so the chart cannot show the future."""
    title = "How sure is the prediction?"
    d = (preds[preds["stage"] <= current_stage].groupby("stage")["sigma"].first().sort_index())
    if d.empty:
        return empty_figure(title, "Run a session to see it")
    fig = go.Figure(go.Scatter(
        x=[stage_labels[s] for s in d.index], y=d.to_numpy(), mode="lines+markers+text",
        text=[f"±{v:.1f}" for v in d], textposition="top center", textfont=dict(color=INK, size=12),
        line=dict(color=ACCENT, width=3), marker=dict(size=9, color=ACCENT),
        hovertemplate="%{x}<br>typical error ±%{y:.2f} places<extra></extra>",
    ))
    fig = _style(fig, title, "typical error of the finishing order, in places (lower = surer)", 6)
    fig.update_yaxes(autorange=True, showgrid=True, gridcolor=GRID, range=[0, float(d.max()) * 1.3],
                     title="± places", tickfont=dict(color=INK_3))
    fig.update_xaxes(showgrid=False, categoryorder="array", categoryarray=[stage_labels[s] for s in sorted(stage_labels)])
    return fig


def backtest_chart(summary: pd.DataFrame, stage_labels: dict[int, str], metric: str = "spearman") -> go.Figure:
    """Mean rank correlation per stage, one bar per predictor."""
    title = "Backtest: predictor vs baseline"
    if summary.empty:
        return empty_figure(title, "No backtest available")
    palette = {0: INK_3, 1: ACCENT, 2: "#5B9BD5"}
    fig = go.Figure()
    for i, (name, g) in enumerate(summary.groupby("predictor", sort=False)):
        g = g.sort_values("stage")
        fig.add_bar(name=name, x=[stage_labels[s] for s in g["stage"]], y=g[metric],
                    marker=dict(color=palette.get(i, FALLBACK), cornerradius=3),
                    text=[f"{v:.2f}" for v in g[metric]], textposition="outside",
                    textfont=dict(color=INK_2, size=11))
    fig = _style(fig, title, "Spearman correlation with the real finishing order, mean over 2026 races (higher = better)",
                 6, legend=True)
    fig.update_layout(barmode="group", bargap=0.25)
    fig.update_yaxes(autorange=True, showgrid=True, gridcolor=GRID, range=[0, 1], tickfont=dict(color=INK_3))
    return fig
