from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.analysis.fundamentals import score_pair
from app.models.fundamental import EconomicEvent
from app.models.live_intelligence import LiveIntelligence


def event(title: str, actual: str, forecast: str) -> EconomicEvent:
    return EconomicEvent(
        event_id=title,
        country="United States",
        currency="USD",
        title=title,
        timestamp=datetime.now(UTC),
        importance="High",
        actual=Decimal(actual),
        forecast=Decimal(forecast),
    )


def intelligence(
    impact: str,
    confidence: float,
    timestamp: datetime = datetime(2026, 9, 25, tzinfo=UTC),
) -> LiveIntelligence:
    return LiveIntelligence(
        news_id="live-1",
        timestamp=timestamp,
        title="Fed signals policy change",
        source_name="Reuters",
        currencies=("USD",),
        event_type="CENTRAL_BANK",
        policy_implication="Potential monetary-policy change.",
        market_impact=impact,
        confidence=confidence,
    )


def test_known_indicator_gets_directional_evidence() -> None:
    result = score_pair(
        "USDJPY",
        events=[event("GDP", "3.0", "2.0")],
        news=[],
    )
    assert result.direction == "BUY"
    assert result.score > 0


def test_score_pair_ignores_future_events_when_as_of_is_supplied() -> None:
    historical = EconomicEvent(
        event_id="historical",
        country="United States",
        currency="USD",
        title="GDP",
        timestamp=datetime(2026, 9, 24, tzinfo=UTC),
        importance="High",
        actual=Decimal("3.0"),
        forecast=Decimal("2.0"),
    )
    future = EconomicEvent(
        event_id="future",
        country="United States",
        currency="USD",
        title="GDP",
        timestamp=datetime(2026, 9, 26, tzinfo=UTC),
        importance="High",
        actual=Decimal("10.0"),
        forecast=Decimal("2.0"),
    )
    result = score_pair(
        "USDJPY",
        events=[historical, future],
        news=[],
        as_of=datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert result.score == Decimal("1.5")


def test_unknown_indicator_does_not_get_guessed_direction() -> None:
    result = score_pair(
        "USDJPY",
        events=[event("Unknown Surprise", "300", "100")],
        news=[],
    )
    assert result.direction == "NEUTRAL"
    assert result.score == 0


def test_live_intelligence_contributes_to_matching_currency() -> None:
    result = score_pair(
        "USDJPY",
        events=[],
        news=[],
        live_intelligence=(intelligence("POSITIVE", 0.8),),
    )

    assert result.score == Decimal("0.8")
    assert result.direction == "BUY"
    assert any("Live: Fed signals policy change" in evidence for evidence in result.evidence)


def test_live_intelligence_does_not_affect_unrelated_pair() -> None:
    result = score_pair(
        "EURJPY",
        events=[],
        news=[],
        live_intelligence=(intelligence("POSITIVE", 0.8),),
    )

    assert result.score == Decimal("0")
    assert result.direction == "NEUTRAL"


def test_live_intelligence_respects_as_of_timestamp() -> None:
    future = intelligence(
        "POSITIVE",
        0.8,
        timestamp=datetime(2026, 9, 26, tzinfo=UTC),
    )
    result = score_pair(
        "USDJPY",
        events=[],
        news=[],
        live_intelligence=(future,),
        as_of=datetime(2026, 9, 25, tzinfo=UTC),
    )

    assert result.score == Decimal("0")


class _CalendarStub:
    def get_events(self, *, countries, start=None, end=None):
        assert "united states" in countries
        return []


class _NewsStub:
    def get_news(self, *, currencies=(), start=None, end=None, limit=50):
        assert currencies == ("USD", "JPY")
        return []


def test_build_pair_bias_orchestrates_provider_data() -> None:
    from app.analysis.fundamentals import build_pair_bias

    result = build_pair_bias(
        "USDJPY",
        calendar=_CalendarStub(),
        news=_NewsStub(),
        as_of=datetime(2026, 9, 25, tzinfo=UTC),
    )
    assert result.instrument == "USDJPY"
    assert result.direction == "NEUTRAL"


def test_build_pair_bias_rejects_naive_timestamp() -> None:
    from app.analysis.fundamentals import build_pair_bias

    with pytest.raises(ValueError, match="timezone-aware"):
        build_pair_bias(
            "USDJPY",
            calendar=_CalendarStub(),
            news=_NewsStub(),
            as_of=datetime(2026, 9, 25),
        )


def test_fundamental_strength_normalizes_pair_bias() -> None:
    from app.analysis.fundamentals import fundamental_strength

    strong = score_pair(
        "USDJPY",
        events=[event("GDP", "10.0", "2.0") for _ in range(10)],
        news=[],
    )
    neutral = score_pair("USDJPY", events=[], news=[])

    assert fundamental_strength(strong) == 1.0
    assert fundamental_strength(neutral) == 0.0
