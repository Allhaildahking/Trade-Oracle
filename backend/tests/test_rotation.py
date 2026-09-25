import pytest

from app.analysis.rotation import (
    MIN_EVALUATION_DAYS,
    MIN_SETUPS_OBSERVED,
    evaluate_candidates,
)
from app.models.candidate import CandidateEvaluation, CandidateStatus


def evaluation(
    instrument: str,
    expectancy: float | None,
    win_rate: float | None,
    *,
    days: int = MIN_EVALUATION_DAYS,
    setups: int = MIN_SETUPS_OBSERVED,
) -> CandidateEvaluation:
    return CandidateEvaluation(
        instrument=instrument,
        status=CandidateStatus.EVALUATION,
        evaluation_days=days,
        setups_observed=setups,
        expectancy_r=expectancy,
        win_rate=win_rate,
    )


def test_rotation_requires_all_three_candidates() -> None:
    with pytest.raises(ValueError, match="all three"):
        evaluate_candidates((evaluation("USDCAD", 0.4, 0.6),), active_instrument="USDCAD")


def test_rotation_does_not_replace_on_insufficient_evidence() -> None:
    result = evaluate_candidates(
        (
            evaluation("USDCAD", 0.2, 0.55),
            evaluation("AUDUSD", 0.8, 0.65, days=3),
            evaluation("NZDUSD", 0.7, 0.64, setups=2),
        ),
        active_instrument="USDCAD",
    )
    assert result.active_instrument == "USDCAD"
    assert not result.changed


def test_rotation_promotes_stronger_sustained_candidate() -> None:
    result = evaluate_candidates(
        (
            evaluation("USDCAD", 0.2, 0.55),
            evaluation("AUDUSD", 0.8, 0.65),
            evaluation("NZDUSD", 0.5, 0.60),
        ),
        active_instrument="USDCAD",
    )
    assert result.active_instrument == "AUDUSD"
    assert result.changed
    statuses = {item.instrument: item.status for item in result.evaluations}
    assert statuses["AUDUSD"] == CandidateStatus.ACTIVE
    assert statuses["USDCAD"] == CandidateStatus.STASIS


def test_rotation_keeps_active_when_reserve_is_not_stronger() -> None:
    result = evaluate_candidates(
        (
            evaluation("USDCAD", 0.8, 0.65),
            evaluation("AUDUSD", 0.7, 0.66),
            evaluation("NZDUSD", 0.6, 0.62),
        ),
        active_instrument="USDCAD",
    )
    assert result.active_instrument == "USDCAD"
    assert not result.changed


def test_rotation_rejects_invalid_active_pair() -> None:
    with pytest.raises(ValueError, match="candidate instrument"):
        evaluate_candidates(
            (
                evaluation("USDCAD", 0.8, 0.65),
                evaluation("AUDUSD", 0.7, 0.66),
                evaluation("NZDUSD", 0.6, 0.62),
            ),
            active_instrument="EURUSD",
        )
