# Day 2 model notes: questions and answers

Reference notes from building and tuning the race predictor (2026-09-24). Each section answers
a question asked during Day 2, with the measured result. All numbers are from the 2026
expanding-window backtest (14 races) unless marked 2023-26 (84 races). Experiments that were
not adopted ran in a scratch environment, not in this repo.

Current state of the code: `f1cc/predict/` (commit `86f3cd8`).

---

## 1. How the prediction works (the pipeline)

```
 Revealed sessions of THIS weekend            Race results of EARLIER weekends only
 (apply_cutoff: FP1..Q, never the Race)       (form, reliability, training rows, past errors)
            │                                              │
            ▼                                              ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ FeatureBuilder.matrix(year, round, k sessions revealed)              │
 │  one row per driver:                                                 │
 │   prac_rank, prac_gap_pct, lr_rank        (practice pace, long runs) │
 │   sprint_rank, sprint_pos                 (sprint weekends)          │
 │   q_pos, q_gap_pct                        (once Qualifying is shown) │
 │   team_form, driver_form                  (this season, shrunk)      │
 └───────────────┬──────────────────────────────────────────────────────┘
                 │
      ┌──────────┴───────────────┐
      ▼                          ▼
 BASELINE (default)          RIDGE (all seasons / 2026 only)
 score = q_pos               trained on the same stage k of every earlier
   else sprint-quali order   weekend: fill gaps -> standardise -> ridge (alpha=10)
   else practice pace        (falls back to baseline with < 40 training rows)
      │                          │
      └──────────┬───────────────┘
                 ▼
 place = rank of score  ─────────────►  expected_pos (the order shown in the app)
                 │
                 ├─ noise: sigma(place) = a + b·place, fitted to THIS predictor's own
                 │         out-of-sample errors on the previous 40 weekends (finishers)
                 ├─ retirement chance per team: this season's rate, shrunk toward the
                 │         long-run rate (20 pseudo-starts)
                 └─ centre: Baseline after Qualifying = halfway between grid place and
                            gap-to-pole converted into places (time scale, weight 0.5);
                            otherwise the place itself
                 ▼
 Monte Carlo, 20,000 runs: centre + sigma·noise, retirements dropped to the back, re-rank
                 ▼
 p_pos (chance of every finishing position) -> p_win, p_podium  -> charts
```

Nothing after the cutoff can reach a prediction: tests scramble later sessions, the race
itself, later weekends and retirement statuses, and check the output does not change.

## 2. The models and algorithms

| Piece | What it is | How it works |
|---|---|---|
| Baseline | A rule, no fitted order | Finish where you qualify; before Q, sprint-qualifying order; else practice pace |
| Ridge regression | Linear model with a penalty on big weights (`alpha·Σw²`) | Predicts finishing position from 9 relative features; the penalty stops correlated features (practice rank vs long-run rank) getting wild weights |
| Shrinkage | Blending an average toward a neutral value | A team with 1 race of history is pulled hard toward the neutral value; with 10 races its own average dominates |
| Monte Carlo simulation | Repeat the race many times with random noise | Win % = share of runs a driver finishes first. It is not MCTS (tree search) |
| Expanding-window backtest | Honest evaluation over time | To score race N, use only races before N. Never a random split |
| Paired bootstrap | How sure a difference is | Resample the races 4,000 times; if the 95% interval of (model − baseline) excludes 0, the difference is probably real |

## 3. Concepts asked about

- **Neutral P10.5:** the average finishing place of a 20-car field, (1+…+20)/20. Used as "no
  history" in team/driver form: `(sum of positions + 10.5·m) / (races + m)`, m = 4 teams, 2
  drivers. Caveat: 2026 has 22 cars (neutral ≈ 11.5); a small bias ridge partly absorbs.
- **"The bootstrap says the difference isn't real" - good or bad?** Neither. It means the data
  cannot tell the two apart, not that they are equal. With 14 races a modest real edge can
  hide inside the interval. Many comparisons were run, so about 1 in 20 "significant" results
  is expected by chance.
- **Should races 1..N-1 be shuffled?** Which races are used must be chronological (no future
  races). The order of rows inside the training set does not matter for ridge.
- **Brier score:** measured against what actually happened, not against the simulation. Per
  driver `(predicted chance − outcome)²`, outcome 1 if on the podium else 0. Always guessing 3/20
  scores ~0.128; the model scores ~0.06.
- **Winner log-loss:** `−log(chance given to the actual winner)`. Grades only the win %.
- **Spearman:** rank agreement between predicted and real order (1 perfect, 0 random). Grades the
  order for the whole grid.
- **RPS (ranked probability score):** grades each driver's whole distribution of finishing
  positions, so "about P8" is rewarded for a P9 finish and punished for a P18. The whole-grid
  probability score; added to the backtest today.

## 4. Hyperparameters: worth tuning?

| Setting | Effect measured | Verdict |
|---|---|---|
| Simulation runs (20,000) | Win % varies ±1.0 pt between seeds at 1k runs, ±0.3 at 20k, ±0.1 at 200k | Leave |
| Bootstrap resamples (4,000) | Interval edges move by ±0.0004 | Leave |
| Ridge alpha (10) | Mean Spearman 0.672 (alpha 0.01) to 0.678 (alpha 1000) | Barely matters; with ~2,000 rows and few features the data already pins the weights |
| Time-scale weight (0.5) | Chosen on 2022-25; per-race selection flipped on noise because RPS is flat in it | Fixed |

## 5. LightGBM and other algorithms

Why LightGBM is a poor fit here: ~20 rows per race and ~100 races, and the 20 drivers in a race
are not independent (shared weather, safety cars), so the effective sample is closer to the
number of races. Boosted trees have many settings to tune and would fit noise; 2026's new rules
also make older seasons' patterns partly wrong.

Tested on the same backtest (mean Spearman, 14 races × 4 stages):

| Model | Mean |
|---|---|
| Rank-average of baseline and ridge | 0.682 |
| Ridge alpha 1000 | 0.678 |
| Baseline | 0.676 |
| LightGBM lambdarank | 0.673 |
| Ridge alpha 10 / 2026 weighted ×5 | 0.672 / 0.674 |
| LightGBM regression | 0.671 |
| Random forest | 0.670 |

Spread of 0.012: all inside the noise. The rank-average's small pre-Qualifying edge was 1 of ~40
comparisons, so likely chance.

## 6. The data

Stored (from FastF1, one parquet per year, 2022-26):

- `features` (31 columns, one row per driver per session): keys, team and colour, lap counts,
  best lap / gap / pace rank, best sector times, long-run pace / delta / rank / degradation,
  main compound, results (position, grid, status, Q1-Q3).
- `laps` (15 columns): every clean lap with sector times, tyre, stint, long-run delta.
- `stints` (10 columns): tyre stints per driver.
- Built from those: `predictions` (per driver per stage, now with the full `p_pos`
  distribution) and `backtest` (metrics per race × stage × predictor).

What FastF1 offers beyond that:

| Data | In local cache? | Notes |
|---|---|---|
| Laps: speed traps (SpeedI1, SpeedI2, SpeedFL, SpeedST), new-tyre flag, pit in/out, track status, position, deleted laps | Yes | Extracted offline for the experiments |
| Weather (air/track temp, humidity, rain, wind; per minute) | Yes | Not stored |
| Track status (safety car, VSC, red flag) | Yes | Used in experiments |
| Race-control messages | No | Penalties are already in grid positions |
| Telemetry (speed, throttle, brake, gear, X/Y/Z; ~4 samples/s) | No | Hours to download under the rate limit; no cornering-speed channel as such |
| Circuit info (corner positions) | No | |
| Jolpica/Ergast (standings, pit stops, history) | Partly | |

- **Weather worth adding?** Not for prediction: only 2 of 105 races were wet, race-day weather
  is unknown when predicting (using it would leak), and a value shared by every driver cannot
  change the order. Possible commentary flavour only.
- **Sector times** are stored but not used by the model or charts. Best use: a sector-gap chart.

## 7. The 2026 battery / energy hypothesis

Rules checked against Formula1.com, Raceteq, Autosport and The Race: ~50/50 engine/electric
power, MGU-K 350 kW, no MGU-H; harvest limits practice 8.5 MJ, **qualifying 7.0 MJ, race
8.0 MJ** (from Melbourne 2026), down to 5 MJ at energy-hungry tracks like Monza; electric power
tapers above 290 km/h (overtake mode keeps full power to 337 km/h); super clipping (harvesting at
full throttle at the end of straights) is capped at ~2-4 s per lap.

Test (speed-trap drop from qualifying lap to race trim, relative to the field, traps under
290 km/h only):

- The race does cost speed field-wide (5-27 km/h at intermediate/straight traps).
- Practice fade predicts race fade (Spearman 0.50): practice measures something real.
- But even the **race's own** fade barely explains places gained (−0.06), and as a feature it
  made predictions slightly worse (−0.003 to −0.043 Spearman). **Not used.** Good material for a
  chart, not for the model.

## 8. What the race-by-race review found

- Retirements are the biggest error source: Spearman 0.71 with them, 0.87 without. Retirement
  rates differ hugely by team (Aston Martin 50%, Cadillac 39%, Alpine 4% in 2026).
- Pole won 9 of 14 races, but the app gave the pole sitter ~29%.
- Sprint weekends froze the prediction for two steps (sprint sessions unused).
- Monza: Gasly on pole despite P14 practice pace (finished P7); Antonelli won from 19th on the
  grid.
- Not real: team racecraft persistence (−0.16 after adjustment); the actual grid predicts
  worse than qualifying order (0.679 vs 0.717), matching the literature.
- A chart bug: the "How sure" y-axis did not start at 0.

## 9. Changes made, and what they did (after Qualifying, 2026 baseline)

| Change | Result |
|---|---|
| Axis fix | "How sure" chart starts at 0; backtest legend no longer overlaps |
| Noise growing down the order + per-team retirement chance | Winner log-loss 1.45 → 1.19; pole win % 29 → 46 |
| Noise fitted to each predictor's own past (out-of-sample) errors | Ridge winner log-loss 1.56 → 1.44 on its own; 1.12 with the above |
| Sprint-qualifying order before Q (chosen on 2024-25: 0.59 vs practice 0.40) | Prediction now moves after sprint quali; 2026 level on average (better in 4 of 5) |
| Time gaps for all drivers (time scale, weight 0.5 from 2022-25) | Winner log-loss 1.23 → **1.02** (2023-26: 1.39 → 1.25, significant); RPS unchanged; pole win % 49 |

Current standings after Qualifying (2026):

| | Spearman | Winner log-loss | Podium Brier | RPS |
|---|---|---|---|---|
| Baseline | **0.712** | **1.02** | **0.064** | **0.104** |
| Auto (app default: best record this season) | 0.707 | 1.03 | 0.065 | 0.105 |
| Ridge, all seasons | 0.706 | 1.21 | 0.072 | 0.107 |
| Ridge, 2026 only | 0.703 | 1.34 | 0.064 | 0.107 |

(Corrected scoring: the backtest first scored each race against the FP1 entry list, which left
out race drivers replaced by an FP1 rookie. Fixed 2026-09-25; conclusions unchanged.)

## 10. Ideas tested and rejected

| Idea | Result |
|---|---|
| Feature screen over all FastF1 data: gap to teammate, long-run rank, new softs used, grid penalty | Correlate with results (stable across seasons) but add nothing beyond qualifying order once learned from earlier races |
| Track overtaking history, safety-car history, lap-1 skill, practice mileage, pit-lane start, team pit times | No signal or sign flips between seasons |
| Front-row-only pole margin | Worked (winner log-loss −0.06), then superseded by the whole-field time scale |
| Weighting this season's errors more when fitting the noise | 2026 winner log-loss worse (1.888 → 1.906); the overstated error is mostly midfield, where it does not affect win/podium |
| Sorting by simulated average / median finishing position | 2026 after Q worse (−0.012, worse in 11 of 14): a retirement is all or nothing, so the average predicts a result that rarely happens |
| Session weighting: long-run rank from FP2 only; one-lap pace weighted FP1×1, FP2×2, FP3×3 | Every effect ≤0.004 Spearman / ≤0.001 RPS, and the sign disagrees between 2023-25 and 2026. FP2 really is the best long-run session (Spearman with race 0.47 vs ~0.30) and FP2 matches race track temperature best, but most drivers only do long runs in FP2 anyway, so the plain average was already mostly FP2 |
| Recency-weighted form (half-life 3 or 6 races) | Only ridge uses form. Slightly better in 2023-25, slightly worse in 2026 after Qualifying; inside the noise. By extension the Kalman filter (a principled version) is unlikely to pay off now |
| Down-weighting 2022-25 for the all-seasons ridge (old seasons ×0.5/0.25/0.1, or old seasons as a prior the current season pulls away from) | Order changes ≤ +0.005 in 2026; winner log-loss worse (1.21 → 1.25-1.35); nothing to choose on 2023-25 (no rule change there). The relative features already transfer across eras, so there is little "wrong" old data to discount |
| Weather, telemetry, speed traps | See sections 6 and 7 |

## 11. Other questions

- **Why is the ridge's ± error smaller - is it surer?** Its ± is fitted to its last 40 races
  (mostly 2025), where it really was better. In 2026 all three predictors are equally accurate
  (1.70-1.71 places off after Q) and all overstate their error (actual ≈ 70-80% of claimed).
- **Does ridge beat the baseline?** Over 2023-26 yes on order: +0.11 after the first session,
  +0.02 after Qualifying, all significant. In 2026 no (−0.006 after Q, worse in 10 of 14): the
  2022-25 patterns it learned stopped paying off under the new rules.
- **Why use winner log-loss if we predict the whole grid?** It only grades the win %. The order
  is graded by Spearman, the whole-grid probabilities by RPS (added today); changes are now
  checked against all of them.
- **Shouldn't the gaps between all drivers count?** Yes - that became the time scale. It helps
  the win % a lot; the whole-grid RPS barely moves because midfield hundredths are swamped by
  strategy and incidents.
- **Why doesn't the time scale change the predicted order?** Qualifying ranks by lap time, so a
  bigger gap always means further down: converting gaps into places stretches the spacing but
  cannot make anyone pass. (Rare exception: a Q1 lap faster than a Q2 lap after the track
  improved.) The shown order is the qualifying order by design.

- **Does the model improve through the season?** It learns from every earlier 2026 race. The
  2026-only ridge was behind the baseline after Qualifying in races 1-7 (-0.028) and level in
  races 8-14 (+0.002); single races swing by ±0.05-0.09, so trends need several races to judge.
- **Is qualifying just too strong in 2026?** For finishers, yes: qualifying vs finish 0.87 in 2026,
  the highest of 2022-26, and the winner came from the front row in 13 of 14 races. Ridge's
  after-Qualifying edge shrinks as qualifying gets more decisive (2023 +0.055 → 2026 -0.006).
- **Is the baseline a model?** The order is a rule (qualifying, else sprint quali, else practice);
  the probabilities are a Monte Carlo simulation whose inputs (error size, retirement rates, gap
  per place) are fitted to past data.

## 12. Open items

- Default predictor: now **Auto** - whichever predictor has the best record on this season's
  earlier races (baseline until 3 races). 2026: +0.018 / +0.014 before Qualifying, -0.005 after.
- Chained model (practice → qualifying → race): most promising idea left; post-Day-3.
- Day 3: generated commentary, deployment on Streamlit Cloud (browser step), polish.
- Known gaps: race incidents are modelled as independent per driver; the pole sitter is still
  slightly under-rated (49% vs 9 of 14 won).
