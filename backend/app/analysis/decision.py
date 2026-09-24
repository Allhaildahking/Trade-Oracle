"""High-level decision contract.

This is a deliberately small foundation. Actual scoring and evidence rules will
be implemented only after data-provider contracts and backtest fixtures exist.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionContext:
    fundamental_score: float
    technical_score: float
    news_blocked: bool = False


def decide(context: DecisionContext) -> str:
    """Return a safe placeholder decision.

    V1 foundation deliberately refuses to manufacture a trade before the real
    analytical engines and validation data exist.
    """

    if context.news_blocked:
        return "BLOCKED"

    if not 0.0 <= context.fundamental_score <= 1.0:
        raise ValueError("fundamental_score must be between 0 and 1")

    if not 0.0 <= context.technical_score <= 1.0:
        raise ValueError("technical_score must be between 0 and 1")

    return "NO_TRADE"

