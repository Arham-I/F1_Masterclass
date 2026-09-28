"""(Re)build data/overtakes_<year>.parquet - on-track overtakes per race - from FastF1.
backfill.py keeps it up to date as races are added; run this after changing race_overtakes()
or to fill past seasons (cached sessions: seconds each).

    python scripts/build_overtakes.py --years 2022 2023 2024 2025 2026
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore", category=FutureWarning)

import pandas as pd  # noqa: E402

from f1cc import data, features, store  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--years", type=int, nargs="+", required=True)
for year in ap.parse_args().years:
    rows = [features.race_overtakes(data.load_session(year, rnd, "Race"), year, rnd) for rnd in data.completed_rounds(year)]
    store.write("overtakes", year, pd.concat(rows, ignore_index=True))
    print(year, len(rows), "races", flush=True)
