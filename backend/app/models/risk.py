"""Domain model for the deterministic risk and validation gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

RiskDecision = Literal["TRADE", "WATCH", "WAIT", "NO_TRADE", "BLOCKED"]


@dataclass(frozen=True, slots=True)
class RiskValidation:
    instrument: str
    decision: RiskDecision
    valid: bool
    reasons: tuple[str, ...]
    checked_at: datetime
    expires_at: datetime | None = None
