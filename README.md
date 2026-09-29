# F1 Race Weekend Companion

A companion app that follows a Formula 1 weekend session by session. After each session
(FP1 → FP2 → FP3 → Qualifying, and Sprint sessions on sprint weekends) it refreshes the charts and
updates a prediction of the race result - for a past weekend replayed step by step, or for a live
weekend before its race.

**Status: Day 3 of a 3-day build.** Built: data pipeline, replay and live weekends, per-session
charts, race prediction with a backtest, race-result view, generated commentary, a "race starts soon"
banner, and a new website for a general F1 audience (`web/`, Next.js on Vercel). The original
Streamlit app is still in place.

Two front ends read the same data:

- **Website** (`web/`, static Next.js, deployed on Vercel): the fan-facing version. 2026 weekends only,
  a start-light timeline with autoplay, plain-language explanations, race-control style commentary,
  and a "lights out" race reveal. See [web/README.md](web/README.md).
- **Streamlit app** (`app.py`): the original analysis view, including earlier seasons' data and the
  backtest charts.

## What the app does

- **Replay a finished weekend.** Pick a weekend and press **Next session**: sessions are released
  one at a time, and the app can only see what has "happened" so far. The race is never revealed.
- **Follow a live weekend** (🔴 LIVE in the list): the sessions run so far and a real forecast of a
  race that has not happened yet.
- **Per-session charts**: gap to the fastest lap, long-run pace (compared within tyre compound), tyre
  stints.
- **Race prediction** for the whole grid: win / podium / retirement chances to two decimals, next to
  the result of the session it was made after, plus the starting grid once qualifying is done.
- **Race-result view** (sidebar, finished weekends): the real result next to the prediction made
  after any chosen session. Display only - the replay never sees race data.
- **Backtest section**: how each predictor has scored, and a race-by-race chart of whether a model is
  pulling ahead of the simple baseline.

## How the prediction works

Four predictors, and **Auto** (the default) picks between them:

- **Baseline** - finish in qualifying order (before Qualifying: practice pace, or the sprint grid).
- **Grid + recovery** - the baseline, but a fast car starting out of position is expected to move
  forward - more on circuits where overtaking is easy, less at Monaco (Baku 2026: Antonelli
  qualified P16 after a crash → predicted P9, finished P5).
- **Ridge, all seasons / same season** - regression on relative inputs (pace ranks and gaps, long
  runs, sprint results, form, teammate gap, tyre use), trained on earlier races only.
- **Auto** - at each stage, whichever predictor has the best record on this season's earlier races.

Percentages come from simulating the race 20,000 times, with retirement chances per team and
uncertainty sized - and, for the baseline and Grid + recovery, shaped (wider before Qualifying,
tighter for the front six after it) - from each predictor's own past mistakes. Full description:
[docs/model.md](docs/model.md).

## How good is it

Scored on the first 15 races of 2026 (R1-R15), each predicted using only what was known at the time
(expanding-window backtest). After Qualifying:

| | Order (Spearman ↑) | Winner log-loss ↓ | Podium Brier ↓ | Whole-grid RPS ↓ |
|---|---|---|---|---|
| Baseline | 0.697 | 0.78 | 0.070 | 0.108 |
| Grid + recovery | **0.709** | 0.75 | 0.070 | **0.107** |
| **Auto** (default) | 0.704 | **0.745** | 0.069 | 0.108 |
| Ridge, all seasons | 0.699 | 1.18 | 0.075 | 0.110 |
| Ridge, same season | 0.692 | 1.34 | **0.068** | 0.110 |

The model is **frozen** at tag `frozen-2026-r15b`; races from R16 on are an untouched holdout
(results in [docs/evaluation.md](docs/evaluation.md#6-frozen-model-and-holdout)).
2026 has been unusually qualifying-dominated, so beating the grid order is hard; over 2023-26 the
models' edges are larger and significant (e.g. Grid + recovery +0.018 after Qualifying). What each
score means, all stages, and how differences are judged: [docs/evaluation.md](docs/evaluation.md).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads only the files in `data/`; it needs neither FastF1 nor network access.

## Keep it up to date

```bash
pip install -r requirements-dev.txt
python scripts/auto_update.py --push        # pull what's due, re-score, re-export, publish
```

`auto_update.py` runs the steps below for any session that finished 30 minutes ago (the race, 60)
and does nothing if none has. Put it on a timer during a weekend — see
[docs/season-checklist.md](docs/season-checklist.md) for the cron line and its caveats. To run the
steps yourself:

```bash
python scripts/backfill.py --years 2026 --in-progress   # during a weekend: sessions run so far
python scripts/backfill.py --years 2026                 # after the race
python scripts/backtest.py                              # re-score and re-predict
python scripts/export_site.py                           # refresh the website's data
python -m pytest tests
```

Then commit `data/` and push; the deployed app reloads its code on its own. The full routine,
traps (rate limits, pulling too early, offline rebuilds) and what to re-check through the season:
[docs/season-checklist.md](docs/season-checklist.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/model.md](docs/model.md) | Pipeline diagram, every input, the predictors, how percentages are made, data rules, settings |
| [docs/evaluation.md](docs/evaluation.md) | The backtest, every metric with formulas and worked examples, significance rules, current results |
| [docs/experiments.md](docs/experiments.md) | Everything tried - kept and rejected - with numbers |
| [docs/faq.md](docs/faq.md) | Concepts and questions (methods, Auto, grid vs qualifying, the data) |
| [docs/season-checklist.md](docs/season-checklist.md) | Weekly routine, periodic re-checks, end-of-season tasks, ideas not built yet |

## Project layout

```
web/                       website (Next.js static export for Vercel) - see web/README.md
app.py                     Streamlit app (presentation only)
f1cc/data.py               FastF1 access, event-match guard, live-session timing
f1cc/features.py           per-driver-per-session features from FastF1 sessions
f1cc/store.py              parquet storage in data/, starting grids
f1cc/replay.py             replay cutoff: which sessions are visible
f1cc/charts.py             Plotly figures (no Streamlit inside)
f1cc/predict/              feature matrix, baseline, recovery, ridge, simulation
f1cc/backtest_summary.py   summaries, significance, Auto
f1cc/commentary.py         commentary sentences built only from computed numbers at each cutoff
f1cc/site_export.py        stored data -> JSON for the website (race result kept in a separate file)
scripts/backfill.py        pull sessions from FastF1 into data/
scripts/backtest.py        backtest + stored predictions
scripts/export_site.py     write the website's JSON (web/data, web/public/data)
scripts/auto_update.py     scheduled: pull finished sessions, re-score, re-export, optionally push
scripts/build_overtakes.py on-track overtakes per race (circuit overtaking ease)
scripts/experiments/       reusable experiments (season trend, feature retest, chained model)
tests/                     leakage, data integrity, freshness, app smoke tests
```

## Data and known limitations

- Data from [FastF1](https://github.com/theOehrly/Fast-F1) (Formula 1's public timing feed),
  2022-2026, 460+ sessions. FastF1 is rate-limited (~500 calls/hour); cached sessions rebuild in
  minutes.
- Long-run pace is confounded by fuel load, which the feed does not expose; wet sessions have few
  long runs (dry compounds only).
- Race incidents (crashes, safety cars) are modelled as independent per driver. The pole sitter now
  gets ~67% on average after Qualifying (10 of 15 poles converted in 2026).
- After FP1 alone, a race driver who sat out FP1 for a rookie is missing from the prediction until
  FP2. Practice "best laps" may include steward-deleted laps (qualifying uses official times).
- Team colours change between and within seasons, and several are close (Williams / Red Bull), so
  every chart mark is also labelled with the driver code.

*Unofficial fan project. Not affiliated with or endorsed by Formula 1, the FIA, or any team.*
