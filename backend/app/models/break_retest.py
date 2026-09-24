"""Domain models for deterministic break-and-retest detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

BreakRetestDirection = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True, slots=True)
class BreakRetest:
    instrument: str
    timeframe: str
    timestamp: datetime
    direction: BreakRetestDirection
    level: Decimal
    break_price: Decimal
    retest_price: Decimal
    close_price: Decimal
