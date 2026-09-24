from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.liquidity import map_liquidity
from app.models.market import Candle


def candle(index: int, high: str, low: str) -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe="1H",
        timestamp=datetime(2026, 1, 5, tzinfo=UTC) + timedelta(hours=index),
        open=Decimal(low),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(low),
        is_complete=True,
    )


def test_maps_previous_day_high_low() -> None:
    candles = [
        candle(0, "1.10", "1.08"),
        candle(1, "1.12", "1.09"),
        candle(24, "1.11", "1.07"),
    ]

    levels = map_liquidity(candles)

    day_levels = [level for level in levels if level.kind.startswith("PREVIOUS_DAY")]
    assert any(level.kind == "PREVIOUS_DAY_HIGH" and level.price == Decimal("1.12") for level in day_levels)
    assert any(level.kind == "PREVIOUS_DAY_LOW" and level.price == Decimal("1.08") for level in day_levels)


def test_maps_previous_week_high_low() -> None:
    candles = [
        candle(0, "1.10", "1.08"),
        candle(1, "1.15", "1.07"),
        candle(168, "1.11", "1.09"),
    ]

    levels = map_liquidity(candles)

    week_levels = [level for level in levels if level.kind.startswith("PREVIOUS_WEEK")]
    assert any(level.kind == "PREVIOUS_WEEK_HIGH" and level.price == Decimal("1.15") for level in week_levels)
    assert any(level.kind == "PREVIOUS_WEEK_LOW" and level.price == Decimal("1.07") for level in week_levels)


def test_maps_completed_session_high_low() -> None:
    candles = [
        candle(8, "1.10", "1.08"),
        candle(9, "1.12", "1.09"),
        candle(13, "1.11", "1.07"),
    ]

    levels = map_liquidity(candles)

    london = [level for level in levels if level.session == "LONDON"]
    assert any(level.kind == "SESSION_HIGH" and level.price == Decimal("1.12") for level in london)
    assert any(level.kind == "SESSION_LOW" and level.price == Decimal("1.09") for level in london)
