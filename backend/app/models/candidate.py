"""Candidate-pair rotation models."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CandidateStatus(StrEnum):
    EVALUATION = "EVALUATION"
    ACTIVE = "ACTIVE"
    STASIS = "STASIS"
    UNDER_REVIEW = "UNDER_REVIEW"


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    instrument: str
    status: CandidateStatus
    evaluation_days: int
    setups_observed: int
    expectancy_r: float | None = None
    win_rate: float | None = None
    notes: str = ""
