# FAQ: concepts and questions from building the model

Short answers to the questions that came up while building and tuning the predictor. Details:
[model.md](model.md), [evaluation.md](evaluation.md), [experiments.md](experiments.md).

---

## The methods

| Term | What it is here |
|---|---|
| **Regression** | Predicting a number (finishing position) from inputs, as a weighted sum |
| **Ridge regression** | Regression with a penalty on large weights, so correlated inputs (practice rank vs long-run rank) don't get wild weights. Small data needs it |
| **Standardising** | Putting inputs on the same scale before the penalty, so it treats them fairly |
| **Shrinkage** | Blending an average toward a neutral value by how much data there is: one race of form counts little, ten count a lot |
| **Overfitting** | Learning the noise of past races, which fails on new ones |
| **Monte Carlo simulation** | Running the race 20,000 times with random noise and counting outcomes. Not MCTS (tree search for games) |
| **Backtesting** | Predicting past races as if live, then scoring against the real result |
| **Expanding window** | For race N, use only races before N; then add race N. Never a random split |
| **Data leakage** | Future information slipping into a prediction; the tests scramble it and check nothing changes |
| **Paired bootstrap** | Resampling the races to see how much a difference between two versions wobbles |

**Why is the neutral form value P10.5?** It is the average finishing place of a 20-car field,
(1+…+20)/20: "no history" means midfield. Form = `(sum of positions + 10.5 × m) / (races + m)`, with
`m` = 4 for teams and 2 for drivers. 2026 has 22 cars (neutral ≈ 11.5): a small known wart.

**"The bootstrap says it's not significant" - good or bad?** Neither: the data cannot tell the two
apart. It does not prove they are equal.

**Should training races be shuffled?** Which races are used must be chronological; the row order
inside the training set does not matter for ridge.

**Why not LightGBM?** ~20 rows per race, ~100 races, and the drivers in one race share weather and
safety cars, so the effective sample is closer to the number of races. Trees would fit noise and
need tuning that eats the test set. Tested anyway: no better (see experiments).

## How the model behaves

**Is the baseline a model?** Its *order* is a rule (qualifying, else sprint qualifying, else
practice). Its *percentages* come from a Monte Carlo simulation whose inputs - noise size,
retirement chances, gap per grid place - are fitted to past data.

**Is Grid + recovery just baseline plus recovery?** Yes. Identical before Qualifying; after it, a
driver starting behind his car's pace moves up `0.5 × ease × (grid slot − pace slot)`, where ease
is how easy the circuit is to overtake on (Monaco ~0.4, most tracks ~1). Baku 2026:
Antonelli qualified P16 after a Q1 crash, pace slot ~P2 → predicted P9.

**Does recovery also push back slow cars that qualified high?** No, and on purpose: tested, it
made the order worse. Cars that out-qualify their pace by 5+ places typically finish where they
started (track position, and a good qualifying is often real pace); they only drop in the
prediction when a faster car recovers past them.

**How does Auto work, and does it learn from the latest race?** For each stage it averages each
predictor's Spearman over this season's scored races and uses the best one (the baseline until
three races exist). After a race is backfilled and scored (`backfill.py`, then `backtest.py`), the
next weekend's choice includes it. It follows the season average, not the last race: single races
swing ±0.05-0.09, and tighter windows did worse.

**Does the model improve through the season?** It learns from every earlier race. The same-season
ridge started behind the baseline in 2026 (races 1-7: −0.028) and drew level (races 8-14: +0.002).

**Why is the ridge's "±" smaller - is it surer?** Its ± is fitted to its last 40 races (mostly
2025), where it was better. In 2026 all predictors are about equally accurate after Qualifying,
and all overstate their error (actual ≈ 70-80% of claimed).

**Why doesn't the time scale change the predicted order?** A bigger qualifying gap always means a
worse qualifying position, so converting gaps into places changes the spacing, not who is ahead.
It changes how often neighbours swap - the percentages.

**Why use winner log-loss when we predict the whole grid?** It grades the win % only. The order is
graded by Spearman and the whole-grid percentages by RPS; every change is checked against all.

**Is 2026 qualifying just too strong?** For finishers, yes: 0.87 agreement with the qualifying
order (highest of 2022-26), which is why models that try to beat the grid gain little this year.

## Grid, qualifying order and best lap: three different things

| Thing | Used for |
|---|---|
| **Starting grid** (after penalties) | Shown in the app; not an input. Penalised drivers typically recover the lost places, and qualifying order predicted the finish better |
| **Qualifying classification** | The predicted order after Qualifying |
| **Best lap across Q1-Q3** | How close the cars are (time scale). 16% of drivers set it in an earlier segment than the one that decided their slot; using it predicts better than the last-segment time |

Example, Baku 2026: Verstappen classified P8 on his Q3 time (1:44.081) but set 1:43.706 in Q2, so
the time scale treats him as slightly quicker than his slot. Google's grid shows the last-segment
time; both are correct for their purpose.

## The data

- **Stored** (`data/`, one parquet per table per year, 2022-26): `features` (one row per driver per
  session: pace, long runs, tyres, results, `new_soft_sets`), `laps` (clean laps), `stints`,
  `predictions`, `backtest`; plus `starting_grid.csv` for live weekends.
- **In the FastF1 cache but not stored**: speed traps, weather (per minute), track status.
- **Not downloaded**: telemetry (speed/throttle/brake traces), race-control messages, circuit maps.
- **Weather** is not useful for prediction: only 2 of 105 races were wet, race weather is unknown
  beforehand (using it would leak), and a value shared by all drivers cannot change the order.
- **Sector times** are stored but unused (a sector-gap chart would be their best use).
- **Long runs**: clean dry-tyre stints of 5+ laps (after dropping laps more than 4% off the stint
  median), each lap compared with the field's median on the same compound. No fuel correction -
  fuel loads are not in the feed; tyre-age correction was tested and made it worse.

**Can tracks be ranked by overtaking difficulty?** Yes - by counting on-track passes (order swaps
between green-flag laps, pit stops excluded): Monaco ~3 per race, Las Vegas / Abu Dhabi the most.
The earlier measure (how closely the finish follows the grid) could not: it mostly reflects how
spread out the cars are, and was not even stable across 2000-2025.

## The feedback-loop idea

*"Can't the latest race's backtest result tune the model for the next race?"* It already re-learns
after every race: ridge weights, noise size, retirement rates, form, the recovery strength, and
Auto's choice all update. What stays fixed are a few settings. Re-tuning those from recent races
was backtested (the tuning procedure itself, race by race) and did worse than learning from all
earlier races, because one race is too noisy to tune on.
