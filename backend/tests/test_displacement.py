from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.displacement import detect_displacements
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


def baseline_candles() -> list[Candle]:
    return [
        candle(index, "1.1000", "1.1010", "1.0990", "1.1005")
        for index in range(10)
    ]


def test_detects_bullish_displacement() -> None:
    candles = baseline_candles()
    candles.append(candle(10, "1.1000", "1.1040", "1.0990", "1.1035"))

    result = detect_displacements(candles)

    assert len(result) == 1
    assert result[0].direction == "BULLISH"
    assert result[0].body == Decimal("0.0035")
    assert result[0].average_body == Decimal("0.0005")


def test_detects_bearish_displacement() -> None:
    candles = baseline_candles()
    candles.append(candle(10, "1.1005", "1.1010", "1.0960", "1.0970"))

    result = detect_displacements(candles)

    assert len(result) == 1
    assert result[0].direction == "BEARISH"


def test_normal_candle_is_not_displacement() -> None:
    candles = baseline_candles()
    candles.append(candle(10, "1.1000", "1.1010", "1.0990", "1.1005"))

    assert detect_displacements(candles) == ()


def test_weak_close_is_not_displacement() -> None:
    candles = baseline_candles()
    candles.append(candle(10, "1.1000", "1.1040", "1.0990", "1.1010"))

    assert detect_displacements(candles) == ()


def test_incomplete_candle_is_ignored() -> None:
    candles = baseline_candles()
    candles.append(
        candle(10, "1.1000", "1.1040", "1.0990", "1.1035", complete=False)
    )

    assert detect_displacements(candles) == ()


def test_no_lookahead_in_baseline() -> None:
    candles = baseline_candles()
    candles.append(candle(10, "1.1000", "1.1040", "1.0990", "1.1035"))
    candles.append(candle(11, "1.1035", "1.1045", "1.1030", "1.1040"))

    result = detect_displacements(candles)

    assert len(result) == 1
    assert result[0].timestamp == candles[10].timestamp
