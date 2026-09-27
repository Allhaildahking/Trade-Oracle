from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.live_intelligence import (
    classify_live_news,
    score_live_intelligence,
)
from app.models.fundamental import NewsItem
from app.models.live_intelligence import LiveIntelligence


def news(title: str, summary: str = "", currencies: tuple[str, ...] = ()) -> NewsItem:
    return NewsItem(
        news_id="news-1",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        title=title,
        summary=summary,
        source_name="Reuters",
        url=None,
        currencies=currencies,
        source="tree_news",
    )


def intelligence(
    impact: str,
    confidence: float,
    currencies: tuple[str, ...] = ("USD",),
) -> LiveIntelligence:
    return LiveIntelligence(
        news_id="news-1",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        title="Test headline",
        source_name="Reuters",
        currencies=currencies,
        event_type="CENTRAL_BANK",
        policy_implication="Test implication",
        market_impact=impact,
        confidence=confidence,
    )


def test_classifies_central_bank_headline_and_currency() -> None:
    result = classify_live_news(news("Fed signals slower rate cuts", currencies=()))

    assert result.event_type == "CENTRAL_BANK"
    assert result.currencies == ("USD",)
    assert result.market_impact == "NEUTRAL"
    assert result.confidence > 0.5


def test_preserves_multiple_currencies_and_mixed_impact() -> None:
    result = classify_live_news(
        news(
            "Trump tariff plan creates uncertainty as ECB signals rate hike",
            currencies=("USD", "EUR"),
        )
    )

    assert result.event_type == "CENTRAL_BANK"
    assert result.currencies == ("USD", "EUR")
    assert result.market_impact == "MIXED"
    assert any("uncertainty" in evidence for evidence in result.evidence)


def test_unknown_headline_stays_neutral() -> None:
    result = classify_live_news(news("Company announces new product"))

    assert result.event_type == "OTHER"
    assert result.market_impact == "NEUTRAL"
    assert result.policy_implication == "No specific policy implication classified."


def test_scores_positive_intelligence_for_matching_currency() -> None:
    result = score_live_intelligence(
        intelligence("POSITIVE", 0.82),
        "usd",
    )

    assert result == Decimal("0.82")


def test_scores_negative_intelligence_for_matching_currency() -> None:
    result = score_live_intelligence(
        intelligence("NEGATIVE", 0.65),
        "USD",
    )

    assert result == Decimal("-0.65")


def test_unrelated_currency_and_neutral_impact_contribute_zero() -> None:
    assert score_live_intelligence(intelligence("POSITIVE", 0.82), "EUR") == Decimal("0")
    assert score_live_intelligence(intelligence("NEUTRAL", 0.82), "USD") == Decimal("0")
    assert score_live_intelligence(intelligence("MIXED", 0.82), "USD") == Decimal("0")


def test_score_confidence_is_bounded() -> None:
    assert score_live_intelligence(intelligence("POSITIVE", 1.4), "USD") == Decimal("1")
    assert score_live_intelligence(intelligence("NEGATIVE", -0.2), "USD") == Decimal("0")
