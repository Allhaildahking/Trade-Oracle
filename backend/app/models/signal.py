"""Signal domain model.

The model is intentionally provider-agnostic so signals can be generated from
backtests, live data, or shadow runs using the same structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Direction(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class SignalState(StrEnum):
    WATCH = "WATCH"
    ACTIVE = "ACTIVE"
    BREAKEVEN = "BREAKEVEN"
    TP_HIT = "TP_HIT"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True, slots=True)
class Signal:
    instrument: str
    direction: Direction
    entry: float
    stop_loss: float
    take_profit: float
    confidence: float
    created_at: datetime
    invalidation_reason: str | None = None
    expiry_at: datetime | None = None
    state: SignalState = SignalState.WATCH
    updated_at: datetime | None = None

    @property
    def risk_distance(self) -> float:
        return abs(self.entry - self.stop_loss)

    @property
    def reward_distance(self) -> float:
        return abs(self.take_profit - self.entry)

    @property
    def rr(self) -> float:
        if self.risk_distance == 0:
            return 0.0
        return self.reward_distance / self.risk_distance
