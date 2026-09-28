# Experiments log: what was tried, kept and rejected

Every modelling idea tested so far, with its result. Unless marked otherwise, numbers are
Spearman (order) or winner log-loss / podium Brier / RPS (probabilities) from the backtest in
[evaluation.md](evaluation.md): "2026" = 14 races (15 for the noise-shape change, which came after
Baku), "2023-26" = 84 races. Scripts to repeat the
important ones are in `scripts/experiments/` (see [season-checklist.md](season-checklist.md)).

---

## 1. Kept

| When | Change | Result |
|---|---|---|
| Day 2 | Baseline + ridge + expanding-window backtest | Ridge does not beat the baseline in 2026; does over 2023-26 |
| Day 2 | Retirement chance per team + noise that grows down the order | Winner log-loss after Q 1.45 → 1.19; pole sitter's win % 29 → 46 |
| Day 2 | Noise fitted to each predictor's own out-of-sample errors (not its training fit) | Ridge winner log-loss 1.56 → 1.44 on its own |
| Day 2 | Sprint-qualifying order before Q on sprint weekends (chosen on 2024-25: 0.59 vs practice 0.40) | Prediction now moves after sprint quali; 2026 level (better in 4 of 5) |
| Day 2 | Time scale: qualifying gaps for all drivers, weight 0.5 (chosen on 2022-25) | Winner log-loss 1.23 → 1.02 in 2026, 1.39 → 1.25 over 2023-26; order unchanged |
| Day 2 | Whole-grid RPS added to the backtest; full position distributions stored | - |
| Day 2 | Auto: best predictor by this season's record | 2026 vs baseline +0.018 / +0.014 before Q |
| Day 2 | FP1 stand-ins removed once a later session shows the race line-up | 124 stand-ins removed 2022-26 |
| Day 2b | After-Q ridge inputs passing the second-half rule: teammate gap (all seasons); new softs + weighted practice pace (same season) | +0.002 to +0.004 in second halves; a bet on future seasons |
| Day 3 | Official Q1-Q3 times for qualifying best laps | Fixes deleted laps (2.5% of results) |
| Day 3 | Starting grid shown (not an input); live weekends predicted before the race | - |
| Day 3 | **Grid + recovery** predictor | After Q +0.018 over 2023-26 [+0.007, +0.030], +0.006 in 2026; Auto uses it after Q from R10. Baku (R15): Antonelli P16 → P5, predicted P9 |
| Day 3 | **Noise shape** for baseline and Grid + recovery: scale learned per race, wider before Q, top six tighter after Q | Order unchanged. Winner log-loss better 2023-26 (−0.04 to −0.06), after Q in 3 of 4 seasons; 2026 after Q −0.19/−0.21 (significant); RPS before Q significantly better; podium Brier after Q +0.001 (n.s.). Pole sitter's average win % 49 → 67 |

## 2. Rejected

### Algorithms and settings
| Idea | Result |
|---|---|
| LightGBM (regression, lambdarank), random forest, rank-average blend, other ridge penalties | Mean Spearman 0.670-0.682 vs baseline 0.676: all within noise. Too little data (~20 rows per race, drivers in a race not independent) for tree models |
| More simulation runs / bootstrap resamples | 20,000 runs: win % ±0.3 pt; 4,000 resamples: interval edges ±0.0004. Leave |
| Choosing the time-scale weight race by race (40-race window, by RPS) | Flipped on noise (picked "off" at Monza, where it helped most). Fixed at 0.5 instead |
| Weighting this season's errors more when fitting the noise | 2026 winner log-loss 1.888 → 1.906; the overstated error is mostly midfield |
| Circuit-specific noise (scale by the circuit's past unpredictability) | No effect on any score; ≤ 4 past visits per circuit |
| One overall noise correction for 2026's overstatement | The noise was honest in 2022-25 (actual/claimed 0.95-1.06), only 2026 overstated (0.71); fixed by the *shape* change instead |
| Noise shape for the ridges | Podium Brier and RPS after Q significantly worse; kept at scale 1 |
| Sorting by simulated average / median position | 2026 after Q −0.012, worse in 11 of 14: a retirement is all or nothing |
| Chained model (practice → qualifying → race) | Qualifying-trained model 0.626 vs direct ridge 0.624 for the race: level; no late-season or cross-season gain. Best use: a pole forecast (+0.06 on qualifying) |
| Auto variants (history-based record, last 8 races, RPS criterion, blends) | Before Q, adding earlier seasons' record improves winner log-loss (−0.04, significant); after Q the current rule is best; blends improve RPS but hurt the order. Kept as is by choice |

### Features and data
| Idea | Result |
|---|---|
| Feature screen over all FastF1 data: teammate gap, long-run rank, new softs, grid penalty | Correlate with results across seasons, but add nothing beyond qualifying as plain adjustments (later retested, §1 Day 2b) |
| Track overtaking history, safety-car history, lap-1 skill, practice mileage, pit-lane start, team pit times | No signal, or the sign flips between seasons |
| Driver-at-this-circuit history (places gained, teammate gap at the same circuit before) | Worse in every variant (winner log-loss up to +0.13); at most four earlier visits per driver |
| Front-row pole margin | Worked (−0.06 winner log-loss), superseded by the whole-field time scale |
| Session weighting (FP2-only long runs; FP1×1/FP2×2/FP3×3 pace) as plain changes | ≤ 0.004, signs disagree across seasons. FP2 *is* the best long-run session (0.47 vs ~0.30) and closest to race temperatures, but most long runs are in FP2 anyway |
| Recency-weighted form (half-life 3 / 6) | Within noise; before Q gets significantly worse over the season |
| Down-weighting 2022-25 (×0.5/0.25/0.1, or as a prior) | 2026 order ≤ +0.005, winner log-loss worse; no earlier season improved either |
| Long-run corrections for tyre age, and run length as a fuel proxy | Weaker (0.189 → 0.177 / 0.165); staying fast on old tyres is real race pace |
| In-season race-gain form (places gained vs qualifying before) | Fails the second-half rule |
| Grid penalty (as ridge input or as a qualifying/grid blend) | Grid predicts worse than qualifying order (0.687 vs 0.717 in 2026); penalised drivers typically recover all lost places |
| Time-scale gaps from last-segment times (consistent with the classification) | Worse: 2023-26 winner log-loss 1.27 → 1.46, RPS and podium Brier significantly worse; 16% of best laps come from an earlier segment and are real pace |
| Weather | Only 2 of 105 races wet; race weather unknown beforehand; commentary only |
| Telemetry | Not downloaded (hours under the rate limit); the speed-trap version below was negative |

### The 2026 battery / energy hypothesis
Rules (Formula1.com, Raceteq, Autosport, The Race): ~50/50 engine/electric power, MGU-K 350 kW, no
MGU-H; harvest limits practice 8.5 MJ, qualifying 7.0 MJ, race 8.0 MJ (from Melbourne 2026), down
to 5 MJ at energy-hungry tracks; electric power tapers above 290 km/h (overtake mode keeps it to
337 km/h); super clipping capped at ~2-4 s per lap.

| Test | Result |
|---|---|
| Speed-trap drop from the qualifying lap to race trim, relative to the field (traps < 290 km/h) | Real field-wide (5-27 km/h); practice fade predicts race fade (0.50); but even the race's own fade barely explains places gained (−0.06); as features −0.003 to −0.043 |
| Does a driver's / team's / power-unit supplier's race-vs-qualifying gain repeat within a season? | Yes in 2022-25 (driver level significant every season), not in 2026 (−0.09 to −0.17) |

Conclusion: energy management changes lap times but creates no repeatable winner or loser in the
2026 finishing order. A chart, not a model input.

### Recovery and feedback-loop checks
| Idea | Result |
|---|---|
| Re-tune recovery strength from this season only / last 8 races / last race | Worse than learning from all earlier races (2026: −0.005 significant, −0.006; last race chases noise) |
| Ignore a teammate's crashed qualifying in the pace estimate | −0.002 over 2023-26: averaging three estimates already absorbs it |
| Extra retirement risk when starting at the back | Explained by team reliability; fast cars out of position show none |
| Auto using first-half / second-half-of-season records | Covered by the last-8-races variant: worse; no significant within-season shift found |

## 3. Race-by-race review (2026, first 14 races)

- Retirements are the biggest error: Spearman 0.71 with them, 0.87 without. Rates differ by team
  (Aston Martin 50%, Cadillac 39%, Alpine 4%).
- Pole won 9 of 14; the app first gave the pole sitter ~29% (now ~49%).
- Sprint weekends froze the prediction for two steps (fixed with sprint-qualifying order).
- Monza: Gasly on pole with P14 practice pace (finished P7); Antonelli won from 19th on the grid.
- Qualifying order predicts the finish better than the penalty-adjusted grid (0.717 vs 0.679 then).
- Qualifying is unusually decisive in 2026: finishers vs qualifying order 0.87 (highest of
  2022-26); winner from the front row in 13 of 14. Ridge's after-Q edge shrank from +0.055 (2023)
  to −0.006 (2026).
