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
figure that shrinks as the weekend goes on (before Qualifying there is no grid, so the guess is
much less certain).

- **Baseline:** finish where you qualify; before Qualifying, where practice pace ranks you.
- **Model:** ridge regression on relative features (pace ranks and gaps, long-run rank, in-season
  team and driver form), trained on earlier races only, one model per stage.
- **Backtest:** expanding window over all 14 completed 2026 races, each predicted using only its
  own already-revealed sessions plus earlier races' results. Tests scramble everything a
  predictor must not see and assert the output doesn't change.

**Result (Spearman with the real finishing order, mean of 14 races):** the model does **not** beat
the baseline. After Qualifying the baseline scores 0.73 vs 0.71 (model minus baseline -0.016,
95% interval excludes zero); before Qualifying the model is ahead by 0.00 to 0.02, inside the
noise. The model's podium probabilities are also worse calibrated (Brier) at every stage. So the
baseline is the default and the model is selectable for comparison. With 14 races the intervals are
wide; a larger effect could hide inside them. I tried ridge only; no LightGBM (scikit-learn/LightGBM
are not installed, and ~2k rows with 7 features doesn't call for it).

Known gaps: on sprint weekends stages 2-3 are Sprint Qualifying and Sprint, whose results are
not used as features. Race noise (crashes, safety cars) is modelled as independent per driver.

Regenerate with `python scripts/backtest.py` (needs scipy from requirements-dev.txt).

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
