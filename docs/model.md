# How the prediction model works

Reference for the race predictor in `f1cc/predict/`. How it is tested: [evaluation.md](evaluation.md).
What was tried along the way: [experiments.md](experiments.md). Concepts: [faq.md](faq.md).

---

## 1. Pipeline

```
 THIS weekend: sessions revealed so far            EARLIER weekends: finished races only
 (FP1 ... Qualifying; never the Race)              (form, reliability, race pace, training rows,
                │                                   each predictor's own past errors)
                ▼                                                 ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────┐
 │ FeatureBuilder.matrix(year, round, k sessions revealed) - one row per driver         │
 │  cleaning  FP1 stand-ins dropped once their team has fielded two other drivers        │
 │            qualifying best lap = official Q1-Q3 time (steward-deleted laps excluded)   │
 │  practice  prac_rank, prac_gap_pct, lr_rank (long runs); weighted versions FP1x1..FP3x3│
 │  sprint    sprint_rank (sprint-qualifying order), sprint_pos (sprint result)          │
 │  quali     q_pos, q_gap_pct, tm_delta (gap to teammate), tm_q_pos (teammate's slot)   │
 │  tyres     new_soft (new soft sets already used, vs the field)                        │
 │  history   team_form, driver_form (this season, shrunk toward P10.5)                  │
 │            team_race_pace (team's race long-run pace in this season's earlier races)  │
 └──────────┬──────────────────────┬─────────────────────────────┬──────────────────────┘
            ▼                      ▼                             ▼
      BASELINE               GRID + RECOVERY               RIDGE x 2
      order = qualifying,    = the baseline's order,       (all seasons / same season)
      else sprint-quali      then a car starting behind    linear model on the features,
      order, else practice   its pace slot moves up        trained on earlier weekends at
      pace                   gamma x gap (pace slot =      the same stage; after Qualifying
                             practice + teammate quali     adds tm_delta (all seasons) or
                             + team race pace; gamma       new_soft + weighted pace (same
                             learned from earlier races)   season)
            └──────────────────────┴───────────┬─────────────────┘
                                               ▼
                 place = rank of score  ──►  expected_pos (the predicted order)
                                               │
      ├─ noise sigma(place) = a + b·place, fitted to this predictor's own out-of-sample
      │  errors on the previous 40 weekends (cars that finished)
      ├─ retirement chance per team: this season's rate, shrunk toward the long-run rate
      └─ centre: after Qualifying (baseline, recovery) halfway between the place and the
         gap to pole converted into places ("time scale"); recovery shifts it forward too
                                               ▼
          Monte Carlo, 20,000 races: centre + sigma x noise, retirements to the back, re-rank
                                               ▼
          p_pos (chance of every finishing position) ──► p_win, p_podium
                                               ▼
   AUTO (app default): per stage, the predictor with the best mean Spearman on this season's
   earlier races (the baseline until 3 races exist) - re-decided after every scored race
                                               ▼
   App: whole-grid prediction next to the session result (+ starting grid, display only),
        race-result view, backtest charts
```

**Leak safety.** Nothing after the cutoff reaches a prediction. `FeatureBuilder.matrix` only reads
sessions that `apply_cutoff` has revealed; `FeatureBuilder.result` only answers for weekends that
are already over. Tests scramble later sessions, the race itself, later weekends, retirement
statuses and tyre data, and check that no prediction changes.

## 2. Inputs

| Input | Meaning | Used by |
|---|---|---|
| `prac_rank`, `prac_gap_pct` | Mean practice pace rank and gap (% of the session's best lap) | Baseline before Q, ridge, recovery |
| `lr_rank` | Mean long-run rank (stints of 5+ clean laps, compared within compound) | Ridge |
| `prac_rank_w`, `prac_gap_pct_w` | Practice pace weighted FP1×1, FP2×2, FP3×3 (only once Q is visible) | Same-season ridge after Q |
| `sprint_rank`, `sprint_pos` | Sprint-qualifying order (the sprint grid), sprint result | Baseline before Q; ridge |
| `q_pos`, `q_gap_pct` | Qualifying position, gap to pole (official times) | Everything after Q |
| `tm_delta` | Qualifying gap to the teammate (+ = slower) | All-seasons ridge after Q |
| `tm_q_pos` | Teammate's qualifying position | Recovery (car pace) |
| `new_soft` | New soft sets already used, relative to the field | Same-season ridge after Q |
| `team_form`, `driver_form` | Average finishing position this season, shrunk toward P10.5 | Ridge |
| `team_race_pace` | Team's median race long-run pace in this season's earlier races | Recovery (car pace) |

Missing values: a missing rank means "behind everyone measured"; a missing relative input means
"average". Long-run pace is compound-neutral: each lap is compared with the field's median on the
same tyre. The starting grid after penalties is **shown** but is not an input (see
[faq.md](faq.md#grid-qualifying-order-and-best-lap-three-different-things)).

## 3. Predictors

- **Baseline** - a rule. Before Qualifying: practice pace order (sprint-qualifying order on sprint
  weekends). After Qualifying: the qualifying order. No fitted order; only its uncertainty is fitted.
- **Grid + recovery** (`recovery.py`) - the baseline plus one correction. A car's *pace slot* is
  the field rank of the mean of practice pace, the teammate's qualifying position and the team's
  race pace. A driver qualifying behind his pace slot moves up `gamma × (grid slot − pace slot)`,
  never down. `gamma` is re-learned before each race from all earlier races (0.5 since 2023).
  Identical to the baseline before Qualifying.
- **Ridge, all seasons** (`model.py`) - a penalised linear regression (`alpha = 10`) from the inputs
  to finishing position, one model per stage, retrained on every earlier weekend (2022 onward).
- **Ridge, same season** - the same, trained only on the current season's earlier races; falls
  back to the baseline until it has 40 training rows (~2 races).
- **Auto** (`backtest_summary.pick`) - not a model: for each stage it uses whichever of the four
  has the best average Spearman on this season's already-scored races, the baseline until three
  exist. Once a race is backfilled and scored, the next weekend's choice includes it.

## 4. From an order to percentages

1. **Place** = the predictor's order (1 = predicted winner).
2. **Noise size** `sigma(place) = a + b·place`: fitted to the predictor's *own* mistakes on the
   previous 40 weekends (predictions made without knowing those results), among cars that
   finished. Front-runners' results scatter less than the midfield's.
3. **Retirement chance** per team: its retirement rate so far this season, blended with the rate
   of all earlier races (worth 20 starts). Starting position adds no measurable extra risk.
4. **Centre** (after Qualifying, baseline and recovery): halfway between the grid place and the
   qualifying gap converted into places (gap to pole ÷ the typical gap per place). Two cars 0.01 s
   apart then swap often, two cars 0.5 s apart rarely. The order never changes.
5. **Simulation**: 20,000 races. In each, every car retires with its chance (to the back), the rest
   finish in order of `centre + sigma × random noise`. Win % = share of races won; `p_pos` = the
   share of races in each position. With 20,000 runs percentages are good to about ±0.3 points.

## 5. Data rules worth knowing

- **Live weekends**: `backfill.py --in-progress` pulls sessions ≥ 2 h after they start; the Race
  is never pulled early. Live weekends are predicted but not scored until the race is added.
- **Qualifying times**: FastF1 only flags steward-deleted laps when race-control messages are
  loaded (they are not), so the qualifying best lap uses the official Q1-Q3 times.
- **FP1 stand-ins**: a driver seen only in FP1 is dropped once his team has fielded two other
  drivers since - not merely for missing a session (crash repairs, a wet FP2).
- **Circuit names** change in the feed (Monaco → "Monte Carlo" 2026, Miami → "Miami Gardens"
  2025+); anything keyed on circuit needs an alias table.
- **Starting grid** for a live weekend comes from `data/starting_grid.csv` (hand-entered from two
  published sources; FastF1 only has the grid with the race result).

## 6. Settings

| Setting | Value | Where | How chosen |
|---|---|---|---|
| `TIME_WEIGHT` | 0.5 | `baseline.py` | Best on 2022-25; 2026 an unseen test |
| `gamma` (recovery) | learned per race, 0.5 now | `recovery.py` | Best on all earlier races |
| `ALPHA` (ridge) | 10 | `model.py` | Fixed up front; 0.01-1000 barely differ |
| `ERROR_WINDOW` | 40 weekends | `base.py` | Fixed |
| `DNF_SHRINK` | 20 starts | `base.py` | Fixed |
| `TEAM_SHRINK`, `DRIVER_SHRINK` | 4, 2 races | `base.py` | Fixed |
| `PRIOR_POS` | 10.5 | `base.py` | Midpoint of a 20-car field (2026 has 22: a known wart) |
| `MIN_RACES` (Auto) | 3 | `backtest_summary.py` | Fixed |
| Simulation runs | 20,000 | `base.py` | ±0.3 pt precision |
