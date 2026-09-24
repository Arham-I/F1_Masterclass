"""Replay mode: release a past weekend one session at a time, as if it were happening now.

The cutoff is the *only* thing that decides what the app may see. Every consumer (charts,
predictors, commentary) receives data through :func:`apply_cutoff`, so nothing downstream
can peek at a session that has not "happened" yet. This is also what makes the backtest fair.

No FastF1 import here: a Weekend is built purely from the derived features table.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

RACE_LIKE = ("Race", "Sprint")


@dataclass(frozen=True)
class Weekend:
    year: int
    round: int
    event_name: str
    location: str
    event_date: str
    sessions: tuple[str, ...]  # in running order, including the Race

    @classmethod
    def from_features(cls, features: pd.DataFrame, year: int, round_number: int) -> "Weekend":
        w = features[(features["year"] == year) & (features["round"] == round_number)]
        if w.empty:
            raise KeyError(f"no data for {year} round {round_number}")
        order = (w[["session", "session_idx"]].drop_duplicates()
                 .sort_values("session_idx")["session"].tolist())
        first = w.iloc[0]
        return cls(year, round_number, str(first["event_name"]), str(first["location"]),
                   str(first["event_date"]), tuple(order))

    @property
    def replayable(self) -> tuple[str, ...]:
        """Sessions that can be revealed. The Race is never revealed: it is the answer."""
        return tuple(s for s in self.sessions if s != "Race")

    def label(self) -> str:
        return f"R{self.round:02d} · {self.event_name} · {self.location}"


@dataclass(frozen=True)
class Cutoff:
    """How many replayable sessions have been revealed so far (0 = nothing yet)."""
    weekend: Weekend
    revealed: int = 0

    def __post_init__(self):
        if not 0 <= self.revealed <= len(self.weekend.replayable):
            raise ValueError(f"revealed={self.revealed} out of range")

    @property
    def visible(self) -> tuple[str, ...]:
        return self.weekend.replayable[: self.revealed]

    @property
    def current(self) -> str | None:
        return self.visible[-1] if self.revealed else None

    @property
    def next_session(self) -> str | None:
        return None if self.is_done else self.weekend.replayable[self.revealed]

    @property
    def is_done(self) -> bool:
        return self.revealed >= len(self.weekend.replayable)

    def advance(self) -> "Cutoff":
        return self if self.is_done else Cutoff(self.weekend, self.revealed + 1)

    def reset(self) -> "Cutoff":
        return Cutoff(self.weekend, 0)


def apply_cutoff(df: pd.DataFrame, cutoff: Cutoff) -> pd.DataFrame:
    """Rows of ``df`` belonging to this weekend AND to already-revealed sessions only."""
    w = cutoff.weekend
    mask = (
        (df["year"] == w.year)
        & (df["round"] == w.round)
        & df["session"].isin(cutoff.visible)
    )
    return df[mask]
