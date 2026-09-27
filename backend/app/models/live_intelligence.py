"""Canonical live-market intelligence models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

LiveImpact = Literal["POSITIVE", "NEGATIVE", "MIXED", "NEUTRAL"]
LiveEventType = Literal[
    "CENTRAL_BANK",
    "GOVERNMENT",
    "POLITICS",
    "TRADE_POLICY",
    "GEOPOLITICAL",
    "MACRO",
    "MARKET",
    "OTHER",
]


@dataclass(frozen=True, slots=True)
class LiveIntelligence:
    """Structured interpretation of a live headline.

    This model records evidence and interpretation separately from trading
    decisions. It must not directly produce BUY or SELL instructions.
    """

    news_id: str
    timestamp: datetime
    title: str
    source_name: str
    currencies: tuple[str, ...]
    event_type: LiveEventType
    policy_implication: str
    market_impact: LiveImpact
    confidence: float
    evidence: tuple[str, ...] = ()
