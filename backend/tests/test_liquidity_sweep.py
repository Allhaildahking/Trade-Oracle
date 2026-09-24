from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.liquidity import map_liquidity
from app.analysis.liquidity_sweep import detect_liquidity_sweeps
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle


def candle(
    hour: int,
    high: str,
    low: str,
    close: str,
    *,
    complete: bool = True,
) -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe="1H",
        timestamp=datetime(2026, 1, 5, hour, tzinfo=UTC),
        open=Decimal(close),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        is_complete=complete,
    )


def level(
    price: str,
    side: str,
    *,
    period_end_hour: int = 8,
) -> LiquidityLevel:
    return LiquidityLevel(
        instrument="EURUSD",
        timeframe="1H",
        kind="PREVIOUS_DAY_HIGH" if side == "BUY_SIDE" else "PREVIOUS_DAY_LOW",
        side=side,
        price=Decimal(price),
        period_start=datetime(2026, 1, 4, tzinfo=UTC),
        period_end=datetime(2026, 1, 5, period_end_hour, tzinfo=UTC),
        label="test",
    )


def test_detects_buy_side_sweep() -> None:
    sweeps = detect_liquidity_sweeps(
        [candle(9, "1.1050", "1.0950", "1.0980")],
        (level("1.1000", "BUY_SIDE"),),
    )

    assert len(sweeps) == 1
    assert sweeps[0].direction == "BEARISH"
    assert sweeps[0].sweep_price == Decimal("1.1050")
    assert sweeps[0].close_price == Decimal("1.0980")


def test_detects_sell_side_sweep() -> None:
    sweeps = detect_liquidity_sweeps(
        [candle(9, "1.1050", "1.0950", "1.1020")],
        (level("1.1000", "SELL_SIDE"),),
    )

    assert len(sweeps) == 1
    assert sweeps[0].direction == "BULLISH"
    assert sweeps[0].sweep_price == Decimal("1.0950")
    assert sweeps[0].close_price == Decimal("1.1020")


def test_close_through_level_is_not_a_sweep() -> None:
    sweeps = detect_liquidity_sweeps(
        [candle(9, "1.1050", "1.0990", "1.1030")],
        (level("1.1000", "BUY_SIDE"),),
    )

    assert sweeps == ()


def test_incomplete_candle_is_ignored() -> None:
    sweeps = detect_liquidity_sweeps(
        [candle(9, "1.1050", "1.0950", "1.0980", complete=False)],
        (level("1.1000", "BUY_SIDE"),),
    )

    assert sweeps == ()


def test_level_not_yet_completed_is_ignored() -> None:
    sweeps = detect_liquidity_sweeps(
        [candle(7, "1.1050", "1.0950", "1.0980")],
        (level("1.1000", "BUY_SIDE", period_end_hour=8),),
    )

    assert sweeps == ()


def test_maps_then_detects_session_sweep() -> None:
    candles = [
        Candle(
            instrument="EURUSD",
            timeframe="1H",
            timestamp=datetime(2026, 1, 5, hour, tzinfo=UTC),
            open=Decimal(close),
            high=Decimal(high),
            low=Decimal(low),
            close=Decimal(close),
            is_complete=True,
        )
        for hour, high, low, close in [
            (8, "1.1000", "1.0900", "1.0950"),
            (9, "1.1050", "1.0920", "1.0980"),
            (13, "1.1080", "1.0910", "1.0990"),
        ]
    ]

    levels = map_liquidity(candles)
    sweeps = detect_liquidity_sweeps(candles, levels)

    london_high = [
        sweep
        for sweep in sweeps
        if sweep.level.session == "LONDON"
        and sweep.level.kind == "SESSION_HIGH"
    ]
    assert len(london_high) == 1
    assert london_high[0].timestamp == datetime(2026, 1, 5, 13, tzinfo=UTC)
