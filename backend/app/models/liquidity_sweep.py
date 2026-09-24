"""Domain models for deterministic liquidity sweeps."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.models.liquidity import LiquidityLevel

SweepDirection = Literal["BEARISH", "BULLISH"]


@dataclass(frozen=True, slots=True)
class LiquiditySweep:
    instrument: str
    timeframe: str
    timestamp: datetime
    direction: SweepDirection
    level: LiquidityLevel
    sweep_price: Decimal
    close_price: Decimal
