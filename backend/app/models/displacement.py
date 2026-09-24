"""Domain models for deterministic displacement detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

DisplacementDirection = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True, slots=True)
class Displacement:
    instrument: str
    timeframe: str
    timestamp: datetime
    direction: DisplacementDirection
    body: Decimal
    range: Decimal
    body_ratio: Decimal
    average_body: Decimal
    close_location: Decimal
