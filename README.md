# F1 Race Weekend Companion

A companion app that follows an F1 weekend session by session. After each session
(FP1 → FP2 → FP3 → Qualifying, plus Sprint sessions on sprint weekends) it refreshes the
charts for that session.

**Status: Day 2 of a 3-day build.** Working: data pipeline, replay mode, three per-session
charts, race-result prediction with a backtest. **Not built yet:** generated commentary,
notifications.

## What you can do in the app

Pick a finished weekend (default: 2026 Spanish GP) and press **Next session**. Replay mode
releases the weekend one session at a time, as if it were happening now, and the app can only
see sessions that have already "happened". The Race is never revealed. Each session shows:

- **Gap to fastest lap**: best valid lap per driver
- **Long-run pace**: lap-time spread on long stints, compared with the field on the *same*
  compound so soft and hard runners are comparable
- **Tyre stints**: every stint per driver, by compound

## Prediction and backtest

After each revealed session the app shows podium and win probabilities plus a typical-error
figure (for cars that finish) that shrinks as the weekend goes on (before Qualifying there is no grid, so the guess is
much less certain).

- **Baseline:** finish in the most recent competitive order: Qualifying once it has run; on a
  sprint weekend before that, Sprint Qualifying (the sprint grid); otherwise practice pace.
- **Model:** ridge regression on relative features (pace ranks and gaps, long-run rank, sprint
  order and result, in-season team and driver form), trained on earlier races only, one model
  per stage.
- **Probabilities:** each driver may retire (team's retirement rate so far this season, shrunk
  toward the long-run rate), and the rest finish in predicted order plus noise that grows down
  the order. The noise is fitted to each predictor's *own* out-of-sample errors on the previous
  40 weekends, not to its training fit. After Qualifying the baseline also uses the **time
  gaps**, not just the order: each car sits halfway between its grid place and its gap to pole
  converted into places, so two cars 0.01s apart are close to a coin flip and two cars 0.5s
  apart are not. The halfway weight was chosen on 2022-25 races only.
- **Backtest:** expanding window over all 14 completed 2026 races, each predicted using only its
  own already-revealed sessions plus earlier races' results. Tests scramble everything a
  predictor must not see (later sessions, the race itself, later weekends, retirements) and
  assert the output doesn't change.

**Result (mean of 14 races, after Qualifying):**

| | Spearman with real order | Winner log-loss | Podium Brier | Whole-grid RPS |
|---|---|---|---|---|
| Baseline | **0.712** | **1.02** | **0.064** | **0.104** |
| Auto (default, see below) | 0.704 | 1.06 | 0.066 | 0.106 |
| Ridge, all seasons | 0.707 | 1.21 | 0.071 | 0.107 |
| Ridge, 2026 only | 0.700 | 1.38 | 0.065 | 0.107 |

Lower is better for everything except Spearman. RPS (ranked probability score) grades each
driver's whole distribution of finishing positions, so it covers the midfield too.

In 2026 the model does **not** beat the baseline on finishing order: -0.006 after Qualifying,
95% interval [-0.020, +0.011]. Over 2023-26 (84 races) it does: +0.11 after the first session,
shrinking to +0.02 after Qualifying, all with intervals above zero. So the 2022-25 patterns it
learns stopped paying off under the 2026 rules, at least early in the season: the 2026-only ridge
starts with nothing to learn from and catches up as races accumulate.

The app's default is therefore **Auto**: at each stage it uses whichever predictor has the best
record on *this season's earlier races* (the baseline until three races exist), re-decided every
race. In 2026 it switched to the 2026-only ridge before Qualifying from round 5-7 on and kept the
baseline after Qualifying. Against always using the baseline: +0.018 after the first session,
+0.014 after the second (interval above zero), -0.005 after the third and -0.008 after
Qualifying (it tried ridge there in four early races). A
race-by-race chart in the app shows how each model's record develops through the season.
Down-weighting 2022-25 inside the all-seasons ridge (or using it only as a prior) was also tried:
no season 2023-26 improved.

Features that only pay off later in a season: every rejected feature was retested on 2023-26 by
whether it helped the *second half* of each season (where an in-season learner has the most
data), in at least 3 of 4 seasons. Three passed and were added to ridge, after Qualifying only:
gap to teammate in qualifying (all-seasons ridge), and new soft-tyre sets already used plus
practice pace weighted towards later sessions (same-season ridge). The gains are small (+0.002 to
+0.004 in second halves, 2026's second half not among the improved) - they are kept as a bet on
future seasons, with Auto deciding whether ridge is used at all. Rejected: grid penalty, FP2-only
long runs, recency-weighted form, down-weighting old seasons, and a new driver-at-this-circuit
history feature (places gained and teammate gap at the same circuit in earlier seasons), which
made predictions worse in every variant.
I also tried LightGBM (regression and lambdarank), random forests, other ridge penalties and
energy-management features built from speed traps; none beat the baseline.

What did help was the probability model. Replacing one error size for every driver with
retirements plus order-dependent noise made the win and podium chances clearly better calibrated:
before, the pole sitter was always given about 29% to win; then about 46%. Using qualifying time
gaps then cut the baseline's winner log-loss after Qualifying from 1.23 to 1.02 in 2026 (1.39 to
1.25 over 2023-26, 84 races, interval below zero) with no change to whole-grid RPS, and the pole
sitter now gets about 49% (in 2026 the pole sitter won 9 of 14).
Sprint Qualifying beat practice pace as a guide on 2024-25 sprint weekends (0.59 vs 0.40); on
2026's five sprint weekends it was better in four and worse in one, and level on average.

Also tested and not adopted: gap to teammate, long-run pace, new tyres used, grid penalties,
track overtaking and safety-car history, lap-1 skill, and weighting recent races when fitting
the noise. Each either added nothing beyond qualifying or made the probabilities worse.

Scoring note: until 2026-09-25 the backtest scored each race against the FP1 entry list, so race
drivers replaced by a rookie in FP1 were left out (up to seven per race, including one winner).
Numbers above use the corrected scoring against everyone who raced; conclusions did not change.

FP1 stand-ins (rookies in their mandatory FP1 outings) are dropped from the prediction once a
later session shows their team with two other drivers.

Known gaps: after FP1 alone the prediction covers the FP1 line-up, so a race driver who sat out
FP1 is missing until FP2. Race incidents (crashes, safety cars) are independent per driver; the pole sitter is
still slightly under-rated.

Regenerate with `python scripts/backtest.py` (needs scipy from requirements-dev.txt). Detailed
notes on every modelling question and experiment: [docs/day2-model-notes.md](docs/day2-model-notes.md).
Routine commands for each race weekend, and experiments to repeat later in the season:
[docs/season-checklist.md](docs/season-checklist.md).

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app reads only the derived files in `data/` and does **not** need FastF1 or network access.

## Rebuild the data (optional)

```bash
pip install -r requirements-dev.txt
python scripts/backfill.py --years 2026            # or 2022 2023 2024 2025
python -m pytest tests
```

Notes from building this:
- FastF1 is rate-limited (~500 API calls/hour). The backfill waits and retries instead of
  skipping, and takes many hours for a cold multi-year pull. Cached sessions rebuild in minutes.
- The backfill skips sessions already in `data/`. After changing `f1cc/features.py`, delete
  `data/*.parquet` and re-run it; otherwise old rows are silently kept. `tests/test_data_freshness.py`
  fails if stored data no longer matches the current code.

## Data and known limitations

- Data comes from [FastF1](https://github.com/theOehrly/Fast-F1), which reads Formula 1's public
  timing feed. Coverage here: 2022-2026, 460 sessions.
- Long-run pace is confounded by fuel load, which the feed does not expose. Treat it as a
  relative signal, not an absolute one.
- Long-run comparison uses dry compounds only, so wet sessions show few or no long runs.
- Official team colours changed mid-season in 2024 and 2025; each round uses its own palette.
- Several team colours are close (e.g. Williams / Red Bull blues), so every mark is also labelled
  with its driver code rather than relying on colour alone.

*Unofficial fan project. Not affiliated with or endorsed by Formula 1, the FIA, or any team.*
