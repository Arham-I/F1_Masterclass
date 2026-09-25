"""Race-by-race: is each predictor pulling ahead of the baseline as the season goes on?

Reads data/backtest_<year>.parquet (run scripts/backtest.py first). Prints, per stage, each
predictor's Spearman minus the baseline's for the first and second half of the season and the
trend per race.  Usage: python scripts/experiments/season_trend.py [--year 2026]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np  # noqa: E402
from scipy.stats import linregress  # noqa: E402

from f1cc import backtest_summary as bts  # noqa: E402
from f1cc import store  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--year", type=int, default=2026)
year = ap.parse_args().year
full = bts.with_auto(store.read("backtest", [year]))
for stage in sorted(full["stage"].unique()):
    t = bts.season_trend(full, stage)
    half = t["round"].max() / 2
    print(f"\nstage {stage} ({'after Qualifying' if stage == 4 else 'before Qualifying'})")
    for name, g in t.groupby("predictor"):
        lr = linregress(g["round"], g["diff"])
        print(f"  {name:36s} 1st half {g[g['round'] <= half]['diff'].mean():+.3f}  2nd half "
              f"{g[g['round'] > half]['diff'].mean():+.3f}  trend/race {lr.slope:+.4f} (p={lr.pvalue:.2f})")
print("\nAuto's picks by round:", {k: [bts.pick(full, r, k).split(' (')[0] for r in sorted(full['round'].unique())]
                                   for k in map(int, sorted(full['stage'].unique()))})
