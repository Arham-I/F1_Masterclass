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
- **Not significant ≠ equal.** With 15 races a modest real effect can hide inside the interval.
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

## 4. Current results (2026, R1-R15: the development races)

| Stage | Predictor | Spearman | Winner log-loss | Podium Brier | RPS |
|---|---|---|---|---|---|
| After 1st session | Baseline | 0.642 | 2.11 | **0.085** | **0.118** |
| | Ridge, all seasons | 0.657 | **1.75** | 0.092 | 0.122 |
| | Ridge, same season | **0.660** | 1.94 | 0.093 | **0.118** |
| | Auto | 0.657 | 1.97 | 0.092 | 0.119 |
| After 2nd session | Baseline | 0.662 | 1.96 | **0.082** | 0.118 |
| | Ridge, same season | **0.678** | 1.85 | **0.082** | **0.115** |
| | Auto | 0.676 | 1.86 | **0.082** | **0.115** |
| After 3rd session | Baseline | 0.682 | 1.80 | **0.076** | **0.113** |
| | Ridge, all seasons | 0.671 | **1.61** | 0.085 | 0.117 |
| | Ridge, same season | **0.684** | 1.80 | 0.079 | 0.114 |
| | Auto | 0.677 | 1.81 | **0.076** | **0.113** |
| **After Qualifying** | Baseline | 0.697 | 0.782 | 0.069 | 0.108 |
| | **Grid + recovery** | **0.709** | 0.765 | 0.070 | **0.107** |
| | Ridge, all seasons | 0.696 | 1.178 | 0.076 | 0.110 |
| | Ridge, same season | 0.692 | 1.341 | **0.068** | 0.110 |
| | **Auto** (app default) | 0.704 | **0.754** | **0.068** | 0.108 |

Grid + recovery equals the baseline before Qualifying (its noise scales are learned separately,
hence tiny differences). Over 2023-26 (84 races): ridge beats the baseline on order at every stage
(+0.11 after the first session, +0.02 after Qualifying, intervals above zero); Grid + recovery
beats it after Qualifying by +0.021 [+0.011, +0.031] (with track-dependent recovery); the time scale cut winner log-loss
1.39 → 1.25, and the noise shape a further 0.04-0.06. In 2026 qualifying has been unusually
decisive (finishers vs qualifying order 0.87), which narrows every model's edge after
Qualifying. Baku (R15, 7 retirements) pulled every order score down.

The after-Qualifying row moved slightly on 2026-10-27 (Auto's log-loss 0.745 → 0.754, Ridge
all-seasons' Spearman 0.699 → 0.696) when the §5 qualifying repair restored 2025 R23. Only this
stage moved, and only on the probability metrics for three of the four models: their predicted
*orders* are unchanged, but the noise widths are calibrated from pooled past error, and that round
had been contributing the error of a model running without a qualifying order. Correcting it makes
the spread slightly tighter and so the log-loss slightly worse — the model is now rightly a little
more confident, and pays more when wrong.

## 5. Scoring corrections

| Date | Problem | Fix |
|---|---|---|
| 2026-09-25 | Races were scored against the **FP1 entry list**, leaving out race drivers replaced by an FP1 rookie (up to seven per race, once the winner) | Score against everyone who raced |
| 2026-09-25 | ~2.5% of qualifying "best laps" were **steward-deleted laps** (FastF1 flags them only with race-control messages) | Official Q1-Q3 times; practice still affected (see the checklist) |
| 2026-10-27 | **2026 R16 and 2025 R23 qualifying stored with an empty results table** (pulled while Formula 1 was gating its API): full lap data, but no classified order and no Q1-Q3 times, so `q_pos` was missing for those rounds | Re-pulled those two qualifying sessions once account access was restored (`backfill.py --refetch`). `tests/test_data_integrity.py` now fails and names the round if it recurs |

Neither of the first two changed a conclusion; all numbers here are after both fixes.

The third is a **data repair, not a model change**, so it does not lift the freeze: it restores an
input that an upstream outage had dropped, and tunes nothing. It does move R16's holdout score,
because stage 4 had been scoring that round without the qualifying order it is supposed to see. No
holdout number had been published beforehand, so the table below reports the corrected values.
Only the affected qualifying sessions were re-pulled: re-pulling their practice sessions too would
have shifted `longrun_delta_s`, which *would* have altered the frozen model's training inputs.

## 6. Frozen model and holdout

From 2026-09-28 the model design is **frozen at git tag `frozen-2026-r15b`**. (An earlier tag,
`frozen-2026-r15`, was lifted before any holdout race to add track-dependent recovery; no holdout
result had been seen.)

| | Races | Role |
|---|---|---|
| Development | 2022 → 2026 R15 (Azerbaijan) | Everything was built, tested and chosen on these |
| **Holdout** | **2026 R16 → R23** | Only measured; no setting, feature or rule changes because of them |

"Frozen" fixes the design, not what the model learns: after every race it still refits ridge,
the noise sizes and shapes, retirement rates, form, the recovery strength and Auto's choice, by the
same rules, from races already run - exactly as it would in real use. A change made in response
to a holdout result ends the holdout for the races that prompted it; any new version then needs
fresh races to be judged. Holdout results are reported separately below as they come in.

| Holdout race | Auto's pick | Spearman | Winner log-loss | Podium Brier | RPS |
|---|---|---|---|---|---|
| R16 Bahrain | Grid + recovery | 0.729 | 0.381 | 0.059 | 0.1141 |
| R17 Singapore | Grid + recovery | 0.869 | 0.640 | 0.047 | 0.0977 |
| R18 United States | Grid + recovery | 0.904 | 0.829 | 0.049 | 0.0742 |
| **Mean (3 races)** | | **0.834** | **0.617** | **0.052** | **0.0953** |
| *R1-R15 development, same metric* | | *0.704* | *0.754* | *0.068* | *0.1077* |

Auto chose **Grid + recovery** after qualifying in all three. The holdout is ahead of the
development races on every metric, which is the opposite of the usual direction — but **three races
prove nothing**: that spread sits well inside the race-to-race variation in §4 (per-race Spearman
across 2026 runs from 0.37 to 0.94), and R18 in particular was an orderly race, the easy kind to
predict. Read this table again at R23. Nothing here is a reason to change the model: under the
freeze rules a change made in response to these numbers would end the holdout.

R16's row is **after** the qualifying data repair in §5. Scored on the broken pull it was 0.716;
the model had been denied the qualifying order it is meant to see at stage 4.

