from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.risk import validate_trade
from app.models.confirmation import Confirmation5M
from app.models.market import Quote
from app.models.risk import RiskValidation
from app.models.trade import TradeCandidate


def trade() -> TradeCandidate:
    return TradeCandidate(
        instrument="EURUSD",
        direction="BUY",
        status="VALID",
        entry=Decimal("1.1010"),
        stop_loss=Decimal("1.0980"),
        take_profit=Decimal("1.1085"),
        risk_distance=Decimal("0.0030"),
        reward_distance=Decimal("0.0075"),
        risk_reward=Decimal("2.5"),
        invalidation=Decimal("1.0980"),
        reasons=("valid",),
    )


def confirmation() -> Confirmation5M:
    return Confirmation5M(
        instrument="EURUSD",
        timeframe="5M",
        direction="BUY",
        status="CONFIRMED",
        structure_events=(),
        displacement=None,
        sweep=None,
        reasons=("confirmed",),
    )


def event(importance: str = "LOW") -> tuple:
    from app.models.fundamental import EconomicEvent

    return (
        EconomicEvent(
            event_id="1",
            country="US",
            currency="USD",
            title="Test event",
            timestamp=datetime(2026, 1, 2, 12, tzinfo=UTC),
            importance=importance,
        ),
    )


def quote() -> Quote:
    return Quote(
        instrument="EURUSD",
        timestamp=datetime(2026, 1, 2, 12, tzinfo=UTC),
        bid=Decimal("1.1009"),
        ask=Decimal("1.1011"),
        mid=Decimal("1.1010"),
        source="test",
    )


def test_trade_when_all_gates_pass() -> None:
    result = validate_trade(
        trade=trade(),
        confirmation=confirmation(),
        setup_regime="TRENDING",
        fundamental_aligned=True,
        checked_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
        quote=quote(),
        economic_events=event(),
    )
    assert isinstance(result, RiskValidation)
    assert result.decision == "TRADE"
    assert result.valid is True


def test_waits_when_quote_is_missing() -> None:
    result = validate_trade(
        trade=trade(),
        confirmation=confirmation(),
        setup_regime="TRENDING",
        fundamental_aligned=True,
        checked_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
        economic_events=event(),
    )
    assert result.decision == "WAIT"


def test_blocks_high_impact_news() -> None:
    result = validate_trade(
        trade=trade(),
        confirmation=confirmation(),
        setup_regime="TRENDING",
        fundamental_aligned=True,
        checked_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
        quote=quote(),
        economic_events=event("HIGH"),
    )
    assert result.decision == "BLOCKED"


def test_blocks_duplicate_and_bad_regime() -> None:
    result = validate_trade(
        trade=trade(),
        confirmation=confirmation(),
        setup_regime="UNSTABLE",
        fundamental_aligned=True,
        checked_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
        quote=quote(),
        economic_events=event(),
        duplicate_active=True,
    )
    assert result.decision == "BLOCKED"


def test_blocks_missing_calendar() -> None:
    result = validate_trade(
        trade=trade(),
        confirmation=confirmation(),
        setup_regime="TRENDING",
        fundamental_aligned=True,
        checked_at=datetime(2026, 1, 2, 12, tzinfo=UTC),
        quote=quote(),
    )
    assert result.decision == "BLOCKED"
