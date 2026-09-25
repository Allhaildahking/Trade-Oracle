"""High-level deterministic decision engine.

The decision engine consolidates already-computed evidence. It does not create
market structure, override risk controls, or ask an LLM to make a trade call.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.fundamentals import fundamental_strength

from app.models.confirmation import Confirmation5M
from app.models.fundamental import PairBias
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate

DECISION_THRESHOLD = 0.60


@dataclass(frozen=True, slots=True)
class DecisionContext:
    fundamental_score: float
    technical_score: float
    pair_bias: PairBias | None = None
    news_blocked: bool = False
    setup: SetupCandidate | None = None
    confirmation: Confirmation5M | None = None
    trade: TradeCandidate | None = None
    risk: RiskValidation | None = None

    @classmethod
    def from_pair_bias(
        cls,
        pair_bias: PairBias,
        *,
        technical_score: float,
        **kwargs: object,
    ) -> DecisionContext:
        return cls(
            fundamental_score=fundamental_strength(pair_bias),
            technical_score=technical_score,
            pair_bias=pair_bias,
            **kwargs,
        )
