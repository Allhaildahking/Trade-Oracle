from datetime import UTC, datetime

import pytest

from app.models.live_intelligence import LiveIntelligence


def test_live_intelligence_captures_structured_impact() -> None:
    item = LiveIntelligence(
        news_id="abc123",
        timestamp=datetime(2026, 9, 27, tzinfo=UTC),
        title="Fed official signals slower rate cuts",
        source_name="Reuters",
        currencies=("USD",),
        event_type="CENTRAL_BANK",
        policy_implication="Less easing is expected than previously priced.",
        market_impact="POSITIVE",
        confidence=0.82,
        evidence=("Central-bank commentary", "Rate-expectation implication"),
    )

    assert item.currencies == ("USD",)
    assert item.event_type == "CENTRAL_BANK"
    assert item.market_impact == "POSITIVE"
    assert item.confidence == 0.82
    assert "Rate-expectation implication" in item.evidence


def test_live_intelligence_rejects_unknown_event_type() -> None:
    with pytest.raises(TypeError):
        LiveIntelligence(
            news_id="abc123",
            timestamp=datetime(2026, 9, 27, tzinfo=UTC),
            title="Headline",
            source_name="Source",
            currencies=("USD",),
            event_type="INVALID",  # type: ignore[arg-type]
            policy_implication="Unknown",
            market_impact="NEUTRAL",
            confidence=0.5,
        )
