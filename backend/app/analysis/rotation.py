"""Deterministic adaptive sixth-pair rotation engine.

Candidate pairs are evaluated under the same strategy and are only eligible for
promotion after enough observation time and setup evidence. Rotation is
deliberately conservative: a single weak period does not replace the active
sixth pair.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import CANDIDATE_INSTRUMENTS, CORE_INSTRUMENTS
from app.models.candidate import CandidateEvaluation, CandidateStatus

MIN_EVALUATION_DAYS = 7
MIN_SETUPS_OBSERVED = 5
MIN_ACTIVE_EXPECTANCY_R = 0.0
MIN_ACTIVE_WIN_RATE = 0.50


@dataclass(frozen=True, slots=True)
class RotationDecision:
    active_instrument: str
    evaluations: tuple[CandidateEvaluation, ...]
    changed: bool
    reason: str


def evaluate_candidates(
    evaluations: tuple[CandidateEvaluation, ...],
    *,
    active_instrument: str,
) -> RotationDecision:
    """Select a sixth pair without rotating on insufficient evidence."""
    _validate_inputs(evaluations, active_instrument)

    eligible = tuple(
        item
        for item in evaluations
        if item.instrument != active_instrument and _eligible_for_promotion(item)
    )
    current = next(item for item in evaluations if item.instrument == active_instrument)

    if not _eligible_for_promotion(current):
        return RotationDecision(
            active_instrument=active_instrument,
            evaluations=_mark_statuses(evaluations, active_instrument, None),
            changed=False,
            reason="active pair remains in place because promotion evidence is insufficient",
        )

    if not eligible:
        return RotationDecision(
            active_instrument=active_instrument,
            evaluations=_mark_statuses(evaluations, active_instrument, None),
            changed=False,
            reason="no reserve pair has sufficient evidence for promotion",
        )

    strongest = max(eligible, key=_ranking_key)
    if _ranking_key(strongest) <= _ranking_key(current):
        return RotationDecision(
            active_instrument=active_instrument,
            evaluations=_mark_statuses(evaluations, active_instrument, None),
            changed=False,
            reason="no reserve pair has stronger sustained evidence than the active pair",
        )

    return RotationDecision(
        active_instrument=strongest.instrument,
        evaluations=_mark_statuses(evaluations, strongest.instrument, active_instrument),
        changed=True,
        reason=f"{strongest.instrument} has stronger sustained evidence than {active_instrument}",
    )


def _eligible_for_promotion(item: CandidateEvaluation) -> bool:
    return (
        item.evaluation_days >= MIN_EVALUATION_DAYS
        and item.setups_observed >= MIN_SETUPS_OBSERVED
        and item.expectancy_r is not None
        and item.win_rate is not None
    )


def _ranking_key(item: CandidateEvaluation) -> tuple[float, float, int]:
    return (
        item.expectancy_r if item.expectancy_r is not None else float("-inf"),
        item.win_rate if item.win_rate is not None else float("-inf"),
        item.setups_observed,
    )


def _mark_statuses(
    evaluations: tuple[CandidateEvaluation, ...],
    active_instrument: str,
    promoted_from: str | None,
) -> tuple[CandidateEvaluation, ...]:
    marked: list[CandidateEvaluation] = []
    for item in evaluations:
        if item.instrument == active_instrument:
            status = CandidateStatus.ACTIVE
        elif promoted_from is not None and item.instrument == promoted_from:
            status = CandidateStatus.STASIS
        elif _eligible_for_promotion(item):
            status = CandidateStatus.STASIS
        else:
            status = CandidateStatus.EVALUATION
        marked.append(
            CandidateEvaluation(
                instrument=item.instrument,
                status=status,
                evaluation_days=item.evaluation_days,
                setups_observed=item.setups_observed,
                expectancy_r=item.expectancy_r,
                win_rate=item.win_rate,
                notes=item.notes,
            )
        )
    return tuple(marked)


def _validate_inputs(
    evaluations: tuple[CandidateEvaluation, ...],
    active_instrument: str,
) -> None:
    allowed = set(CANDIDATE_INSTRUMENTS)
    if active_instrument not in allowed:
        raise ValueError(f"active sixth pair must be a candidate instrument: {active_instrument}")

    if len(evaluations) != len(CANDIDATE_INSTRUMENTS):
        raise ValueError("rotation requires evaluations for all three candidate instruments")

    instruments = tuple(item.instrument for item in evaluations)
    if set(instruments) != allowed:
        raise ValueError("rotation evaluations must contain USDCAD, AUDUSD, and NZDUSD")
    if len(instruments) != len(set(instruments)):
        raise ValueError("rotation evaluations must contain unique instruments")
