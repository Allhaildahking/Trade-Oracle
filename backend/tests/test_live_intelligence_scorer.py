from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.live_intelligence import score_live_intelligence
from app.models.live_intelligence import LiveIntelligence


def intelligence(
    *,
    currencies: tuple[str, ...] = ("USD",),
    impact: str = "POSITIVE",
    confidence: float = 0.82,
) -> LiveIntelligence:
    return LiveIntelligence(
        news_id="news-1",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        title="Fed signals stronger policy support",
        source_name="Reuters",
        currencies=currencies,
        event_type="CENTRAL_BANK",
        policy_implication="Potential change in monetary-policy expectations.",
        market_impact=impact,
        confidence=confidence,
    )


def test_positive_matching_currency_scores_by_confidence() -> None:
    result = score_live_intelligence(intelligence(), "USD")

    assert result == Decimal("0.82")


def test_negative_matching_currency_scores_negative() -> None:
    result = score_live_intelligence(
        intelligence(impact="NEGATIVE", confidence=0.65),
        "USD",
    )

    assert result == Decimal("-0.65")


def test_unrelated_currency_scores_zero() -> None:
    result = score_live_intelligence(intelligence(currencies=("EUR",)), "USD")

    assert result == Decimal("0")


def test_neutral_and_mixed_impacts_score_zero() -> None:
    assert score_live_intelligence(intelligence(impact="NEUTRAL"), "USD") == Decimal("0")
    assert score_live_intelligence(intelligence(impact="MIXED"), "USD") == Decimal("0")


def test_confidence_is_clamped_to_zero_one() -> None:
    assert score_live_intelligence(intelligence(confidence=1.5), "USD") == Decimal("1")
    assert score_live_intelligence(intelligence(confidence=-0.2), "USD") == Decimal("0")
