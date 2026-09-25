"""Derived-data storage: one parquet per table per year under data/.

This is the *only* data path the deployed app uses. FastF1 and its multi-GB cache are
build-time concerns; the parquet files are small enough to commit and deploy.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TABLES = ("features", "laps", "stints")


def path(table: str, year: int) -> Path:
    return DATA_DIR / f"{table}_{year}.parquet"


def write(table: str, year: int, df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    df.to_parquet(path(table, year), index=False)


def _normalize_nulls(df: pd.DataFrame) -> pd.DataFrame:
    """Parquet has no distinct NaN for object/string columns, so a missing value written as
    ``float('nan')`` (e.g. ``main_compound`` for a driver with no dry-tyre laps) comes back as
    Python ``None`` instead - same meaning, different type. Re-widen every object column's
    nulls to ``np.nan`` so a value round-trips identically to what was written, and so
    equality checks (tests, a future predictor comparing live vs stored features) don't have
    to special-case which null flavour they might see.
    """
    for col in df.columns[df.dtypes == object]:
        df[col] = df[col].where(df[col].notna(), np.nan)
    return df


def available_years(table: str = "features") -> list[int]:
    return sorted(int(p.stem.rsplit("_", 1)[1]) for p in DATA_DIR.glob(f"{table}_*.parquet"))


def read(table: str, years: list[int] | None = None) -> pd.DataFrame:
    """Concatenate the per-year files (all available years unless ``years`` is given)."""
    years = years if years is not None else available_years(table)
    frames = [_normalize_nulls(pd.read_parquet(path(table, y))) for y in years if path(table, y).exists()]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


GRID_FILE = DATA_DIR / "starting_grid.csv"


def starting_grid(features: pd.DataFrame, year: int, round_number: int) -> pd.DataFrame:
    """Official starting grid (driver, grid, penalty). From the stored Race once it has run;
    before that from data/starting_grid.csv, entered by hand from published grids, because
    FastF1 only has the grid with the race result. Empty if neither is known."""
    race = features[(features["year"] == year) & (features["round"] == round_number)
                    & (features["session"] == "Race")]
    if len(race) and race["grid"].notna().any():
        g = race[["driver", "grid"]].assign(penalty=np.nan)
        g["grid"] = g["grid"].replace(0, np.nan)            # 0 = pit-lane start
        return g.reset_index(drop=True)
    if GRID_FILE.exists():
        g = pd.read_csv(GRID_FILE)
        g = g[(g["year"] == year) & (g["round"] == round_number)]
        return g[["driver", "grid", "penalty"]].reset_index(drop=True)
    return pd.DataFrame(columns=["driver", "grid", "penalty"])

