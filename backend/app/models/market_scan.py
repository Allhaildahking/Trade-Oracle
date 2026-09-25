"""Domain models for multi-pair market analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CandidateDecision = Literal["TRADE", "WATCH", "WAIT", "NO_TRADE", "BLOCKED"]


@dataclass(frozen=True, slots=True)
class PairAssessment:
    instrument: str
    decision: CandidateDecision
    weighted_score: float
    risk_reward: float | None
    direction: str | None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketScan:
    assessments: tuple[PairAssessment, ...]
    ranked: tuple[PairAssessment, ...]
    active_instruments: tuple[str, ...]
