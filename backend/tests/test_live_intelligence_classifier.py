from datetime import UTC, datetime

from app.analysis.live_intelligence import classify_live_news
from app.models.fundamental import NewsItem


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
