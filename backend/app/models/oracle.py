"""Domain result for a complete Trade Oracle pair analysis."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.confirmation import Confirmation5M
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate


@dataclass(frozen=True, slots=True)
class OracleAnalysis:
    instrument: str
    decision: str
    technical_score: float
    weighted_score: float
    setup: SetupCandidate | None
    confirmation: Confirmation5M | None
    trade: TradeCandidate | None
    risk: RiskValidation | None
    reasons: tuple[str, ...]
