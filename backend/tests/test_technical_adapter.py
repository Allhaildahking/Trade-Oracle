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
from app.models.confirmation import Confirmation5M
from app.models.regime import RegimeSnapshot
from app.models.setup import SetupCandidate
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


def test_analyzer_returns_no_trade_during_regime_warmup() -> None:
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
    assert any("15M regime warm-up requires at least 71" in reason for reason in result.reasons)


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



def test_analyzer_can_produce_a_flagged_technical_only_diagnostic(monkeypatch) -> None:
    from app.backtesting import technical_adapter

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
    snapshot = StructureSnapshot(swings=(swing,), events=(event,))
    regime = RegimeSnapshot(
        instrument="XAUUSDmicro",
        timeframe="15M",
        regime="TRENDING",
        atr=1.0,
        baseline_atr=1.0,
        volatility_ratio=1.0,
        directional_efficiency=0.6,
        range_to_atr=2.0,
        sample_size=20,
    )
    setup = SetupCandidate(
        instrument="XAUUSDmicro",
        timeframe="15M",
        direction="BUY",
        status="CANDIDATE",
        fundamental_score=Decimal("0"),
        regime=regime,
        structure_events=(event,),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=("technical HTF bias: BUY",),
    )
    confirmation = Confirmation5M(
        instrument="XAUUSDmicro",
        timeframe="5M",
        direction="BUY",
        status="CONFIRMED",
        structure_events=(event,),
        displacement=None,
        sweep=None,
        reasons=("5M confirmation passed",),
    )
    monkeypatch.setattr(
        technical_adapter,
        "detect_structure",
        lambda candles: snapshot,
    )
    monkeypatch.setattr(
        technical_adapter,
        "detect_setup_candidate",
        lambda *args, **kwargs: setup,
    )
    monkeypatch.setattr(
        technical_adapter,
        "confirm_5m",
        lambda *args, **kwargs: confirmation,
    )
    monkeypatch.setattr(
        technical_adapter,
        "construct_trade",
        lambda **kwargs: _trade(),
    )
    callback_calls = []
    analyzer = build_technical_only_analyzer(
        instrument="XAUUSDmicro",
        liquidity_levels_at=lambda as_of, history: callback_calls.append(as_of) or (),
    )
    history = {
        "4H": [_candle("4H")],
        "1H": [_candle("1H")],
        "15M": [
            Candle(
                instrument="XAUUSDmicro",
                timeframe="15M",
                timestamp=NOW + timedelta(minutes=15 * index),
                open=Decimal("4000"),
                high=Decimal("4001"),
                low=Decimal("3999"),
                close=Decimal("4000"),
                bid=Decimal("3999.99"),
                ask=Decimal("4000.01"),
                is_complete=True,
            )
            for index in range(71)
        ],
        "5M": [_candle("5M")],
    }

    result = analyzer(NOW + timedelta(minutes=5), history)

    assert result.decision == "TRADE"
    assert result.risk is not None and result.risk.valid
    assert callback_calls == [NOW + timedelta(minutes=5)]
    assert any("TECHNICAL-ONLY DIAGNOSTIC" in reason for reason in result.reasons)
    assert any(
        "economic-calendar filters are intentionally excluded" in reason
        for reason in result.reasons
    )
