"""Domain model for 5M confirmation of a 15M setup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.displacement import Displacement
from app.models.liquidity_sweep import LiquiditySweep
from app.models.structure import StructureEvent

ConfirmationDirection = Literal["BUY", "SELL"]
ConfirmationStatus = Literal["CONFIRMED", "REJECTED"]


@dataclass(frozen=True, slots=True)
class Confirmation5M:
    instrument: str
    timeframe: str
    direction: ConfirmationDirection
    status: ConfirmationStatus
    structure_events: tuple[StructureEvent, ...]
    displacement: Displacement | None
    sweep: LiquiditySweep | None
    reasons: tuple[str, ...]
