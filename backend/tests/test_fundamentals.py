import pytest
from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.fundamentals import score_pair
from app.models.fundamental import EconomicEvent


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


def test_known_indicator_gets_directional_evidence() -> None:
    result = score_pair(
        "USDJPY",
        events=[event("GDP", "3.0", "2.0")],
        news=[],
    )
    assert result.direction == "BUY"
    assert result.score > 0


def test_unknown_indicator_does_not_get_guessed_direction() -> None:
    result = score_pair(
        "USDJPY",
        events=[event("Unknown Surprise", "300", "100")],
        news=[],
    )
    assert result.direction == "NEUTRAL"
    assert result.score == 0


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
