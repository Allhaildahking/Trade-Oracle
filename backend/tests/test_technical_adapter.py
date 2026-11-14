# ruff: noqa: I001
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtesting.technical_adapter import (
    _structure_bias,
    _technical_risk,
    build_technical_only_analyzer,
)
from app.models.market import Candle, Quote
from app.models.structure import StructureEvent, StructureSnapshot, SwingPoint
from app.models.trade import TradeCandidate


NOW = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _candle(timeframe: str, *, minute: int = 0) -> Candle:
    return Candle(
        instrument="XAUUSDmicro",
        timeframe=timeframe,
        timestamp=NOW.replace(minute=minute),
        open=Decimal("4000"),
        high=Decimal("4001"),
        low=Decimal("3999"),
        close=Decimal("4000"),
        bid=Decimal("3999.99"),
        ask=Decimal("4000.01"),
        is_complete=True,
    )


def _trade() -> TradeCandidate:
    return TradeCandidate(
        instrument="XAUUSDmicro",
        direction="BUY",
        status="VALID",
        entry=Decimal("4000"),
        stop_loss=Decimal("3990"),
        take_profit=Decimal("4025"),
        risk_distance=Decimal("10"),
        reward_distance=Decimal("25"),
        risk_reward=Decimal("2.5"),
        invalidation=Decimal("3990"),
        reasons=(),
    )


def test_structure_bias_uses_latest_htf_event_and_marks_it_technical() -> None:
    swing = SwingPoint(
        instrument="XAUUSDmicro",
        timeframe="4H",
        timestamp=NOW,
        price=Decimal("3990"),
        kind="HIGH",
        index=1,
    )
    event = StructureEvent(
        instrument="XAUUSDmicro",
        timeframe="4H",
        timestamp=NOW,
        price=Decimal("4000"),
        kind="BOS",
        direction="BULLISH",
        broken_swing=swing,
    )

    bias = _structure_bias(
        "XAUUSDmicro",
        (StructureSnapshot(swings=(swing,), events=(event,)), StructureSnapshot((), ())),
    )

    assert bias is not None
    assert bias.direction == "BUY"
    assert bias.score == Decimal("0")
    assert "direction derived from 4H BOS" in bias.evidence[0]


def test_analyzer_returns_no_trade_without_htf_directional_evidence() -> None:
    analyzer = build_technical_only_analyzer(instrument="XAUUSDmicro")
    history = {
        "4H": [_candle("4H")],
        "1H": [_candle("1H")],
        "15M": [_candle("15M")],
        "5M": [_candle("5M")],
    }

    result = analyzer(NOW.replace(minute=5), history)

    assert result.decision == "NO_TRADE"
    assert result.trade is None
    assert any("no completed 4H/1H structure event" in reason for reason in result.reasons)


def test_analyzer_rejects_non_chronological_history() -> None:
    analyzer = build_technical_only_analyzer(instrument="XAUUSDmicro")
    history = {
        "4H": [_candle("4H")],
        "1H": [_candle("1H")],
        "15M": [_candle("15M")],
        "5M": [_candle("5M", minute=5), _candle("5M")],
    }

    with pytest.raises(ValueError, match="strictly chronological"):
        analyzer(NOW.replace(minute=10), history)


def test_technical_risk_records_fundamental_and_calendar_exclusions() -> None:
    quote = Quote(
        instrument="XAUUSDmicro",
        timestamp=NOW,
        bid=Decimal("3999.99"),
        ask=Decimal("4000.01"),
        mid=Decimal("4000"),
        source="test",
    )

    risk = _technical_risk(
        trade=_trade(),
        setup_regime="TRENDING",
        quote=quote,
        checked_at=NOW,
        expiry=timedelta(minutes=30),
        max_spread_ratio=Decimal("0.10"),
    )

    assert risk.valid is True
    assert risk.decision == "TRADE"
    assert any(
        "economic-calendar filters are intentionally excluded" in reason
        for reason in risk.reasons
    )
    assert any("not approved for live execution" in reason for reason in risk.reasons)


def test_technical_risk_waits_when_historical_spread_is_missing() -> None:
    risk = _technical_risk(
        trade=_trade(),
        setup_regime="TRENDING",
        quote=None,
        checked_at=NOW,
        expiry=timedelta(minutes=30),
        max_spread_ratio=Decimal("0.10"),
    )

    assert risk.valid is False
    assert risk.decision == "WAIT"
