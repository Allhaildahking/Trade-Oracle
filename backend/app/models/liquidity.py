"""Domain models for deterministic liquidity mapping."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

LiquidityKind = Literal[
    "PREVIOUS_DAY_HIGH",
    "PREVIOUS_DAY_LOW",
    "PREVIOUS_WEEK_HIGH",
    "PREVIOUS_WEEK_LOW",
    "SESSION_HIGH",
    "SESSION_LOW",
]
LiquiditySide = Literal["BUY_SIDE", "SELL_SIDE"]
SessionName = Literal["ASIA", "LONDON", "NEW_YORK"]


@dataclass(frozen=True, slots=True)
class LiquidityLevel:
    instrument: str
    timeframe: str
    kind: LiquidityKind
    side: LiquiditySide
    price: Decimal
    period_start: datetime
    period_end: datetime
    label: str
    session: SessionName | None = None
