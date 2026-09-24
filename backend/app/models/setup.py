"""Domain model for 15M setup candidates."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.models.break_retest import BreakRetest
from app.models.displacement import Displacement
from app.models.fundamental import PairBias
from app.models.liquidity_sweep import LiquiditySweep
from app.models.regime import RegimeSnapshot
from app.models.structure import StructureEvent

SetupDirection = Literal["BUY", "SELL", "NEUTRAL"]
SetupStatus = Literal["CANDIDATE", "REJECTED"]


@dataclass(frozen=True, slots=True)
class SetupCandidate:
    instrument: str
    timeframe: str
    direction: SetupDirection
    status: SetupStatus
    fundamental_score: Decimal
    regime: RegimeSnapshot
    structure_events: tuple[StructureEvent, ...]
    sweep: LiquiditySweep | None
    displacement: Displacement | None
    break_retest: BreakRetest | None
    reasons: tuple[str, ...]
