from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.live_intelligence import score_live_intelligence
from app.models.live_intelligence import LiveIntelligence


def intelligence(
    *,
    currencies: tuple[str, ...] = ("USD",),
    impact: str = "POSITIVE",
    confidence: float = 0.8,
) -> LiveIntelligence:
    return LiveIntelligence(
        news_id="news-1",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        title="Fed signals tighter policy",
        source_name="Reuters",
        currencies=currencies,
        event_type="CENTRAL_BANK",
        policy_implication="Potential change in monetary-policy expectations.",
        market_impact=impact,
        confidence=confidence,
    )


def test_scores_positive_impact_by_confidence() -> None:
    result = score_live_intelligence(intelligence(confidence=0.8), "USD")

    assert result == Decimal("0.8")


def test_scores_negative_impact_by_confidence() -> None:
    result = score_live_intelligence(
        intelligence(impact="NEGATIVE", confidence=0.65),
        "USD",
    )

    assert result == Decimal("-0.65")


def test_neutral_and_mixed_have_no_directional_score() -> None:
    for impact in ("NEUTRAL", "MIXED"):
        assert score_live_intelligence(intelligence(impact=impact), "USD") == Decimal("0")


def test_unaffected_currency_has_no_score() -> None:
    result = score_live_intelligence(intelligence(currencies=("EUR",)), "USD")

    assert result == Decimal("0")


def test_confidence_is_bounded() -> None:
    high = score_live_intelligence(intelligence(confidence=2.0), "USD")
    low = score_live_intelligence(
        intelligence(impact="NEGATIVE", confidence=-1.0),
        "USD",
    )

    assert high == Decimal("1")
    assert low == Decimal("0")
