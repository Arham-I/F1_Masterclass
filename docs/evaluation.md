# How the model is evaluated

How predictions are tested and scored, what every number means, and the current results.
Model description: [model.md](model.md). Everything tried: [experiments.md](experiments.md).

---

## 1. The backtest

Every finished race is predicted **as if it were happening**, then scored against what happened.

- **Expanding window.** To predict race N, a predictor may use only race N's own sessions revealed
  so far and results of races *before* N. Race N+1 then also gets race N's result. Never a random
  split - that would let the model learn from the future.
- **Four stages per race**: after the 1st, 2nd and 3rd session and after Qualifying (on sprint
  weekends the middle stages are Sprint Qualifying and the Sprint).
- **Who is scored**: every driver who raced, including retirements at their classified position.
  Non-starters and FP1 stand-ins are not.
- **Tests** check the no-future rule directly: they scramble what a prediction must not see and
  assert the prediction does not change (`tests/test_predict.py`).
- `scripts/backtest.py` writes `data/backtest_<year>.parquet` (scores) and
  `data/predictions_<year>.parquet` (every prediction, including the full position distribution).

## 2. The metrics

### Spearman correlation - the predicted *order*
How well the predicted order matches the real one: +1 identical, 0 unrelated, −1 reversed.
With `d` = predicted rank − actual finish per driver and `n` drivers:

`rho = 1 − 6·Σd² / (n·(n² − 1))` (equivalently, the correlation of the two sets of ranks)

| Driver | Predicted | Actual | d² |
|---|---|---|---|
| NOR | 1 | 3 | 4 |
| ANT | 2 | 1 | 1 |
| VER | 3 | 2 | 1 |
| HAM | 4 | 5 | 1 |
| LEC | 5 | 4 | 1 |

Σd² = 8 → rho = 1 − 48/120 = **0.60**. Big misses dominate (squared): a car predicted P4 that
retires and is classified P22 adds 324 on its own, which is why retirements are the largest
source of error. Every position counts equally, so the front-focused scores below complement it.
2026 values: ~0.64-0.69 before Qualifying, ~0.70-0.72 after.

### Winner log-loss - the *win %*
`−ln(win chance given to the driver who actually won)`. Lower is better.
37% → 0.99; 10% → 2.30; a uniform guess over 22 cars (4.5%) → 3.09. Only the winner counts, so it
grades exactly the headline number. 2026: ~1.0 after Qualifying, ~1.8-2.2 before.

### Podium Brier score - the *podium %*
For every driver `(podium chance − outcome)²`, outcome 1 if he finished on the podium, else 0;
averaged over the grid. Lower is better. Example: 74% podium and on the podium → 0.07; not on it →
0.55. Always saying 3/20 scores ~0.128; the models score ~0.06-0.09.

### RPS (ranked probability score) - the *whole spread of positions*
Grades each driver's full distribution (`p_pos`). Per driver: cumulative predicted chance of
finishing P1-or-better, P2-or-better, ... vs the cumulative actual (0 before his real position,
1 from it on); sum the squared gaps, divide by (n − 1); average over drivers. 0 is perfect.

| | P1 | P2 | P3 | P4 |
|---|---|---|---|---|
| Predicted chance | 10% | 50% | 30% | 10% |
| Cumulative predicted | 0.10 | 0.60 | 0.90 | 1.00 |
| Actual P2 → cumulative | 0 | 1 | 1 | 1 |
| Gap² | 0.01 | 0.16 | 0.01 | 0 |

RPS = 0.18/3 = **0.06**. Had he finished P4: (0.01 + 0.36 + 0.81)/3 = **0.39** - near misses cost
little, far misses a lot. The only score that judges the midfield's probabilities. 2026: ~0.10-0.12.

### Secondary scores (stored in the backtest table)
| Score | Meaning |
|---|---|
| `top3_overlap` | Share of the real podium that the predicted top 3 contains |
| `winner_hit` | 1 if the predicted winner won |
| `mae_pos` | Average places between predicted and actual finish |

### Numbers the app shows
| Where | Number | Meaning |
|---|---|---|
| Prediction | Win / podium / retirement % | From the simulation (§4 of [model.md](model.md)) |
| "How sure is the prediction?" | ± places | Mean `sigma` over the field: typical error for cars that finish |
| Race-result view | Winner (win chance given) | The winner's `p_win` |
| | Podium picked | How many of the real top 3 were in the predicted top 3 |
| | Order agreement | Spearman for this race |
| | Typical miss | `mae_pos` for this race |
| Backtest section | Bar chart, race-by-race chart, intervals | Mean Spearman per stage; season-to-date Spearman vs the baseline; paired intervals (below) |

## 3. Deciding whether a change is real

- **Paired bootstrap.** Two versions are compared race by race; the per-race differences are
  resampled 4,000 times. If the 95% interval of the mean difference excludes zero, the difference
  is taken as real. Races, not drivers, are the independent units.
- **Not significant ≠ equal.** With 14 races a modest real effect can hide inside the interval.
- **Many comparisons.** About 1 in 20 comparisons is "significant" by chance; results that only
  appear once, in one metric, are treated with suspicion.
- **Choose on one set, test on another.** Settings are picked on 2022-25 (or on earlier races) and
  judged on 2026, which they never saw.
- **Second-half rule** (for features that might pay off as a season goes on): keep a feature if it
  improves the second half of the season in at least 3 of 4 seasons (2023-26) and on average,
  without significantly hurting the whole season. One race swings ±0.05-0.09.

**Which score decides what**: changes to the order (features, recovery, sprint inputs) - Spearman,
with the others as a check; changes to the probabilities (retirements, noise, time scale) -
winner log-loss, podium Brier and RPS (the order does not change); Auto - Spearman only, by choice.

## 4. Current results (2026, 14 scored races)

| Stage | Predictor | Spearman | Winner log-loss | Podium Brier | RPS |
|---|---|---|---|---|---|
| After 1st session | Baseline | 0.639 | 2.22 | 0.085 | 0.118 |
| | Ridge, all seasons | 0.657 | **1.77** | 0.089 | 0.120 |
| | Ridge, same season | **0.660** | 2.01 | 0.091 | **0.117** |
| | Auto | 0.656 | 2.05 | 0.091 | **0.117** |
| After 2nd session | Baseline | 0.663 | 2.05 | **0.081** | 0.116 |
| | Ridge, same season | **0.679** | 1.91 | **0.081** | 0.114 |
| | Auto | 0.678 | 1.93 | **0.079** | **0.113** |
| After 3rd session | Baseline | **0.687** | 1.84 | **0.075** | **0.111** |
| | Ridge, all seasons | 0.674 | **1.65** | 0.083 | 0.115 |
| | Auto | 0.682 | 1.85 | **0.075** | **0.111** |
| **After Qualifying** | Baseline | 0.712 | 1.02 | **0.064** | **0.104** |
| | **Grid + recovery** | **0.717** | 1.00 | 0.066 | **0.104** |
| | Ridge, all seasons | 0.706 | 1.21 | 0.072 | 0.107 |
| | Ridge, same season | 0.700 | 1.38 | 0.065 | 0.107 |
| | **Auto** (app default) | 0.711 | **0.97** | 0.066 | 0.105 |

Grid + recovery equals the baseline before Qualifying. Over 2023-26 (84 races): ridge beats the
baseline on order at every stage (+0.11 after the first session, +0.02 after Qualifying, intervals
above zero); Grid + recovery beats it after Qualifying by +0.018 [+0.007, +0.030]; the time scale
cut winner log-loss 1.39 → 1.25. In 2026 qualifying has been unusually decisive (finishers vs
qualifying order 0.87), which narrows every model's edge after Qualifying.

## 5. Scoring corrections

| Date | Problem | Fix |
|---|---|---|
| 2026-09-25 | Races were scored against the **FP1 entry list**, leaving out race drivers replaced by an FP1 rookie (up to seven per race, once the winner) | Score against everyone who raced |
| 2026-09-25 | ~2.5% of qualifying "best laps" were **steward-deleted laps** (FastF1 flags them only with race-control messages) | Official Q1-Q3 times; practice still affected (see the checklist) |

Neither changed a conclusion; all numbers here are after both fixes.
