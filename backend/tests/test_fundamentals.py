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
