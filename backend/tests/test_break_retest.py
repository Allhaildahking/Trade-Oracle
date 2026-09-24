from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.break_retest import detect_break_retests
from app.models.market import Candle


def candle(
    index: int,
    open_price: str,
    high: str,
    low: str,
    close: str,
    *,
    complete: bool = True,
) -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=datetime(2026, 1, 5, tzinfo=UTC) + timedelta(minutes=15 * index),
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        is_complete=complete,
    )


def test_detects_bullish_break_and_retest() -> None:
    candles = [
        candle(0, "1.1000", "1.1010", "1.0990", "1.1000"),
        candle(1, "1.1000", "1.1030", "1.1000", "1.1025"),
        candle(2, "1.1025", "1.1000", "1.0998", "1.1018"),
    ]

    result = detect_break_retests(candles, levels=(Decimal("1.1000"),))

    assert len(result) == 1
    assert result[0].direction == "BULLISH"
    assert result[0].level == Decimal("1.1000")
    assert result[0].timestamp == candles[2].timestamp


def test_detects_bearish_break_and_retest() -> None:
    candles = [
        candle(0, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(1, "1.1005", "1.1000", "1.0970", "1.0975"),
        candle(2, "1.0975", "1.1002", "1.0968", "1.0980"),
    ]

    result = detect_break_retests(candles, levels=(Decimal("1.1000"),))

    assert len(result) == 1
    assert result[0].direction == "BEARISH"
    assert result[0].level == Decimal("1.1000")


def test_failed_retest_is_not_detected() -> None:
    candles = [
        candle(0, "1.1000", "1.1010", "1.0990", "1.1000"),
        candle(1, "1.1000", "1.1030", "1.1000", "1.1025"),
        candle(2, "1.1025", "1.1040", "1.1000", "1.0995"),
    ]

    assert detect_break_retests(candles, levels=(Decimal("1.1000"),)) == ()


def test_retest_expiry_is_respected() -> None:
    candles = [
        candle(0, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(1, "1.1005", "1.1030", "1.1005", "1.1025"),
        candle(2, "1.1025", "1.1040", "1.1015", "1.1030"),
        candle(3, "1.1030", "1.1040", "1.1020", "1.1035"),
        candle(4, "1.1035", "1.1040", "1.1000", "1.1010"),
    ]

    assert detect_break_retests(
        candles,
        levels=(Decimal("1.1000"),),
        max_retest_bars=2,
    ) == ()


def test_incomplete_candle_is_ignored() -> None:
    candles = [
        candle(0, "1.1000", "1.1010", "1.0990", "1.1005"),
        candle(1, "1.1005", "1.1030", "1.1000", "1.1025"),
        candle(2, "1.1025", "1.1000", "1.0998", "1.1018", complete=False),
    ]

    assert detect_break_retests(candles, levels=(Decimal("1.1000"),)) == ()
