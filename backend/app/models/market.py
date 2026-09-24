"""Canonical market-data models used by every provider adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

Timeframe = Literal["4H", "1H", "15M", "5M"]


@dataclass(frozen=True, slots=True)
class Candle:
    instrument: str
    timeframe: Timeframe
    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    source: str = ""
    is_complete: bool = True


@dataclass(frozen=True, slots=True)
class Quote:
    instrument: str
    timestamp: datetime
    bid: Decimal | None
    ask: Decimal | None
    mid: Decimal
    source: str
