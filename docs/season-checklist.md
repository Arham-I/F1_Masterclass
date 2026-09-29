# Season checklist: routine runs, re-checks and ideas for later

Reminders for keeping the companion current through the rest of 2026 and into 2027, and for
the experiments worth repeating once more races exist. Background on every decision: [model.md](model.md),
[evaluation.md](evaluation.md), [experiments.md](experiments.md). All commands run from the repo root with the dev
environment (`pip install -r requirements-dev.txt`).

---

## 1. Every race weekend

### The short version: let it run itself

`scripts/auto_update.py` does the whole routine below. It pulls any session that finished 30
minutes ago (the race, 60 — post-race penalties can still move the order), re-scores, re-exports
the website, and with `--push` commits and pushes so Vercel redeploys.

```bash
python scripts/auto_update.py --dry-run     # what is due right now, changes nothing
python scripts/auto_update.py               # pull + re-score + re-export
python scripts/auto_update.py --push        # ...and publish
```

It is cheap when idle: it reads the local schedule and the stored parquet, and exits without
touching the network if nothing is due. A full run with one new session takes about 90 seconds.
One run at a time (`.auto_update.lock`; a lock older than 3 h is ignored as stale).

Run it on a timer through a race weekend. Every 15 minutes is plenty:

```cron
*/15 * * * * cd /path/to/F1_Masterclass && .venv/bin/python scripts/auto_update.py --push >> /tmp/f1cc.log 2>&1
```

Two things to know before relying on it:

- **The machine has to be awake.** A laptop asleep through qualifying runs nothing, and cron does
  not catch up on missed runs — though the next run that *does* fire pulls everything still
  outstanding, so a missed tick only delays the update.
  **Cloud CI is not an alternative:** F1 blocks datacenter IPs from `livetiming.formula1.com`
  (403), so a GitHub Action cannot pull session data at all — checked 2026-09-29, and
  `.github/workflows/fastf1-probe.yml` re-checks it in a minute if that ever changes. Anything
  running the pull needs a residential connection.
- **`--push` commits and pushes on its own.** Start without it for a weekend and check what lands
  in `git status` before letting it publish.

Still manual: the **starting grid** after qualifying, and the **holdout table** after each race
(both below). Neither blocks the site.

### The steps it runs

| When | Run | Why |
|---|---|---|
| After each session (FP1, FP2, FP3, Q; 30 min after it ends) | `python scripts/backfill.py --years 2026 --in-progress` | Pulls the finished sessions of the live weekend so the app shows a real forecast (listed as 🔴 LIVE) |
| Then | `python scripts/backtest.py` | Writes predictions for the live weekend (predicted, not scored) |
| After Qualifying, once penalties are published | add the starting grid to `data/starting_grid.csv` (two sources; `tests/test_live.py` checks it) | FastF1 only has the grid with the race result; the app shows it next to the prediction |
| After the race | `python scripts/backfill.py --years 2026` then `python scripts/backtest.py` | Adds the Race (and its on-track overtake count); the weekend is now scored and joins the season trend |
| Then (after every backtest, live or finished) | `python scripts/export_site.py` | Refreshes the website's JSON in `web/` (calendar, replay files, race results, accuracy); offline once the backfill has run |
| Then | `python -m pytest tests` | Leak, integrity and freshness tests must pass |
| Then | add the race's Auto after-Q scores to the holdout table in `docs/evaluation.md` §6 | Frozen model: report, don't tune (see the freeze rules there) |
| Then | commit `data/*.parquet` and `web/data`, `web/public/data`, push; reboot the Streamlit app (Manage app → Reboot) | Both deployed front ends only read committed files; Vercel rebuilds the website on push |

Traps:
- **Pulling too early.** The backfill skips any (round, session) already stored, so a session
  pulled before FastF1 had all its data stays incomplete forever. If a live session looks thin
  (fewer than 20 drivers, few laps), delete that round from `data/*_2026.parquet` and re-pull.
  This is also why the race waits 60 minutes rather than 30: a stewards' penalty applied after the
  flag changes the classification, and a race stored before it lands keeps the provisional order.
  If a penalty is announced later, delete that round and re-pull.
  A session that over-runs its slot (red flags, a postponement) is handled automatically: for a
  weekend whose race has not run, the backfill refuses to store a session the timing feed has not
  called over (`Finalised`/`Ends`), printing `wait ...` and leaving it for the next run.
- **Rate limit.** FastF1 allows ~500 API calls/hour. A weekend is well under that; a multi-season
  rebuild is not (the backfill waits it out).
- **Offline rebuilds** (after changing `f1cc/features.py`): delete `data/{features,laps,stints}_*.parquet`
  and rebuild from the local cache. Call `data._enable_cache()` *before*
  `fastf1.Cache.offline_mode(True)` (enabling the cache resets offline mode), and run behind
  `HTTPS_PROXY=http://127.0.0.1:9` so nothing can reach the network. Takes ~3 minutes.

## 2. Re-checks every ~4 races

| Check | Command | Look for / act when |
|---|---|---|
| Is a model pulling ahead of the baseline? | `python scripts/experiments/season_trend.py` | 2nd-half gap turning positive for a ridge. Auto switches on its own; this is for understanding. Also in the app: Backtest → "Race by race" chart |
| Rejected features that might mature | run `feature_retest.py` for `control`, `+gain_form`, `+penalty`, `+lr_fp2`, `+form_hl3`, `+track`, `+old_x0.5` (both `all` and `season`), then `evaluate_retest.py` | A `PASS` = 2nd half better in ≥ 3 seasons and on average. Add it to `AFTER_Q` in `f1cc/predict/model.py` (or to `FEATURES` if it helps before Qualifying too), rerun the backtest |
| The three Day 2b additions still earning their place | same script with `+tm_delta all`, `combo_season season` | If their 2nd-half gains turn negative across seasons, remove them from `AFTER_Q` |
| Recovery strength | `RecoveryPredictor(...).gamma(year, round)` and Auto's picks (`season_trend.py`) | γ is re-learned from all earlier races each weekend; if 2026 keeps showing no recovery, it drifts down on its own |
| Chained model (practice → qualifying → race) | `python scripts/experiments/chained_gate.py` | Model A beating the direct ridge on *race* order by more than ~0.01 across seasons |
| Race-vs-qualifying gains start persisting in 2026 | Not scripted: correlate each driver's mean places gained vs qualifying in earlier 2026 races with the next race's (method: [experiments.md](experiments.md), battery section) | Positive persistence again at driver/team level → retest `+gain_form` |

Parallel runs: `printf '%s\n' "control all" "+gain_form all" ... | xargs -P 4 -L 1 python scripts/experiments/feature_retest.py --out experiments_out`
(then `python scripts/experiments/evaluate_retest.py experiments_out`). ~5-10 min per run.

## 3. End of the 2026 season

- [ ] **Time-scale weight** (`TIME_WEIGHT = 0.5` in `f1cc/predict/baseline.py`): re-choose on
      2022-2026. In 2026 higher weights scored better (1.0 > 0.75 > 0.5 on winner log-loss), but it
      was deliberately not tuned on the test season.
- [ ] **Neutral position for form** (`PRIOR_POS = 10.5` in `f1cc/predict/base.py`) assumes 20 cars;
      2026 has 22 (midpoint 11.5). Make it depend on field size and check the backtest.
- [ ] **Regenerate backtests for every season** (`python scripts/backtest.py --year 2025` etc.) so
      the app's backtest section can show more than one season.
- [ ] **README / notes numbers**: refresh the results tables with the full 2026 season.
- [ ] **Circuit names**: the feed renames locations (Monaco → "Monte Carlo" 2026, Miami → "Miami
      Gardens" 2025+). Check the 2027 calendar for new renames before relying on circuit history.
- [ ] **Team names and colours** change between (and within) seasons; `repair_teams` and the
      per-round palette handle it, but look at the charts after round 1.

## 4. Start of 2027

- [ ] Backfill 2027 as it happens (§1). The same-season ridge starts with nothing and falls back
      to the baseline for ~3 races; Auto starts on the baseline until 3 races exist. Expected.
- [ ] Decide whether 2026 now belongs in the all-seasons ridge's training data unchanged (it is
      the same regulation era as 2027, unlike 2022-25).
- [ ] Retest the regulation-sensitive ideas with 2026 as history: down-weighting pre-2026 seasons
      (`+old_x0.5`), the energy/speed-trap features ([experiments.md](experiments.md); needs speed traps
      extracted - see §5 below), and circuit history (Madrid gets its first previous visit).
- [ ] FastF1 upgrade: bump `requirements-dev.txt`, then run `tests/test_data_freshness.py` - a
      new FastF1 can change extracted values silently.

## 5. Improvement ideas not built yet

| Idea | Status / evidence | Effort |
|---|---|---|
| **Qualifying / pole forecast after practice** (Model A from `chained_gate.py`) | Beats the practice order at predicting qualifying by +0.06 Spearman; a new app output, not a race-model change | ~1 h |
| Race line-up after FP1 | After FP1 only, a race driver who sat out FP1 for a rookie is missing until FP2. Needs the entry list (e.g. previous race's line-up per team) | ~1 h |
| Kalman filter for team pace (upgrades) | Deprioritised: the simpler recency-weighted form did not help | ~4 h |
| Speed-trap energy features | Extraction script was scratch-only; speed traps (`SpeedI1/I2/FL/ST`) are in the FastF1 cache but not stored. Add them to `features.py` if revisiting | ~1 h + test |
| Telemetry clipping chart (speed traces on straights) | Good analysis chart for 2026 energy management; not useful for the model (no race-to-race persistence) | Hours of download |
| Retirements by cause / safety-car likelihood | Race incidents are modelled as independent per driver; safety-car history did not predict error in the screen | ? |
| Deleted laps in practice | Qualifying now uses official Q times; practice "best laps" can still include steward-deleted laps, because race-control messages are not loaded (not cached for past sessions: ~1 API call per session to fetch) | ~1 h + rebuild |
| Weather line in commentary | Stored in the cache (per minute), not extracted. Commentary flavour only | ~30 min |

## 6. Ideas already rejected (do not redo without new data)

Tyre-age and fuel-proxy long-run corrections; battery proxies from speed-trap fade and from
race-vs-qualifying gains; recency-weighted noise fitting; sorting by simulated average
position; LightGBM / random forest; lap-1 skill, practice mileage, pit-lane starts, team pit
times, track overtaking and safety-car history. Details and numbers: [experiments.md](experiments.md).
