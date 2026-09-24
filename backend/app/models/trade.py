"""Domain model for a constructed trade candidate."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

TradeDirection = Literal["BUY", "SELL"]
TradeStatus = Literal["VALID", "REJECTED"]


@dataclass(frozen=True, slots=True)
class TradeCandidate:
    instrument: str
    direction: TradeDirection
    status: TradeStatus
    entry: Decimal | None
    stop_loss: Decimal | None
    take_profit: Decimal | None
    risk_distance: Decimal | None
    reward_distance: Decimal | None
    risk_reward: Decimal | None
    invalidation: Decimal | None
    reasons: tuple[str, ...]
