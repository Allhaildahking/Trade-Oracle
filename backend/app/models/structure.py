"""Domain models for deterministic technical market structure."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

SwingKind = Literal["HIGH", "LOW"]
StructureKind = Literal["BOS", "CHoCH"]
StructureDirection = Literal["BULLISH", "BEARISH"]


@dataclass(frozen=True, slots=True)
class SwingPoint:
    instrument: str
    timeframe: str
    timestamp: datetime
    price: Decimal
    kind: SwingKind
    index: int


@dataclass(frozen=True, slots=True)
class StructureEvent:
    instrument: str
    timeframe: str
    timestamp: datetime
    price: Decimal
    kind: StructureKind
    direction: StructureDirection
    broken_swing: SwingPoint


@dataclass(frozen=True, slots=True)
class StructureSnapshot:
    swings: tuple[SwingPoint, ...]
    events: tuple[StructureEvent, ...]
