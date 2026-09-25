"""High-level deterministic decision engine.

The decision engine consolidates already-computed evidence. It does not create
market structure, override risk controls, or ask an LLM to make a trade call.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import (
    FUNDAMENTAL_WEIGHT,
    MINIMUM_RR,
    TECHNICAL_WEIGHT,
)
from app.models.confirmation import Confirmation5M
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate

DECISION_THRESHOLD = 0.60


@dataclass(frozen=True, slots=True)
class DecisionContext:
    fundamental_score: float
    technical_score: float
    news_blocked: bool = False
    setup: SetupCandidate | None = None
    confirmation: Confirmation5M | None = None
    trade: TradeCandidate | None = None
    risk: RiskValidation | None = None

    @property
    def weighted_score(self) -> float:
        return (
            self.fundamental_score * FUNDAMENTAL_WEIGHT
            + self.technical_score * TECHNICAL_WEIGHT
        )


def decide(context: DecisionContext) -> str:
    """Return one deterministic V1 decision.

    Existing lower-level gates retain ownership of their checks. This function
    only consolidates their outputs into the public decision vocabulary.
    """
    _validate_scores(context)

    if context.news_blocked:
        return "BLOCKED"

    if context.risk is not None:
        if context.risk.decision == "BLOCKED":
            return "BLOCKED"
        if context.risk.decision == "WAIT":
            return "WAIT"

    if context.setup is None or context.setup.status != "CANDIDATE":
        return "NO_TRADE"

    if context.confirmation is None or context.confirmation.status != "CONFIRMED":
        return "WATCH"

    if context.trade is None or context.trade.status != "VALID":
        return "NO_TRADE"

    if context.trade.risk_reward is None or context.trade.risk_reward < MINIMUM_RR:
        return "NO_TRADE"

    if context.risk is None or not context.risk.valid:
        return "WAIT"

    if context.weighted_score < DECISION_THRESHOLD:
        return "NO_TRADE"

    return "TRADE"


def _validate_scores(context: DecisionContext) -> None:
    for name, score in (
        ("fundamental_score", context.fundamental_score),
        ("technical_score", context.technical_score),
    ):
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
