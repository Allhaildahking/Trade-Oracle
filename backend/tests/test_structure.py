from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.structure import detect_structure, detect_swings
from app.models.market import Candle


def candle(index: int, high: str, low: str, close: str) -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        is_complete=True,
    )


def test_detects_confirmed_swing_high_and_low() -> None:
    candles = [
        candle(0, "1.0", "0.8", "0.9"),
        candle(1, "1.2", "0.9", "1.1"),
        candle(2, "1.5", "1.0", "1.4"),
        candle(3, "1.2", "0.9", "1.0"),
        candle(4, "1.0", "0.6", "0.7"),
        candle(5, "1.1", "0.8", "1.0"),
    ]

    swings = detect_swings(candles, left=1, right=1)

    assert [(s.kind, s.index, s.price) for s in swings] == [
        ("HIGH", 2, Decimal("1.5")),
        ("LOW", 4, Decimal("0.6")),
    ]


def test_detects_close_confirmed_bos() -> None:
    candles = [
        candle(0, "1.0", "0.8", "0.9"),
        candle(1, "1.2", "0.9", "1.1"),
        candle(2, "1.5", "1.0", "1.4"),
        candle(3, "1.2", "0.9", "1.0"),
        candle(4, "1.0", "0.6", "0.7"),
        candle(5, "1.1", "0.8", "1.0"),
        candle(6, "1.7", "0.9", "1.6"),
    ]

    snapshot = detect_structure(candles)

    assert len(snapshot.events) == 1
    event = snapshot.events[0]
    assert event.kind == "BOS"
    assert event.direction == "BULLISH"
    assert event.broken_swing.kind == "HIGH"
    assert event.broken_swing.price == Decimal("1.5")
