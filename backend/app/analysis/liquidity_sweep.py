"""Deterministic liquidity sweep detection."""

from __future__ import annotations

from datetime import UTC

from app.models.liquidity import LiquidityLevel
from app.models.liquidity_sweep import LiquiditySweep
from app.models.market import Candle


def _utc(timestamp):
    if timestamp.tzinfo is None:
        raise ValueError("candle timestamps must be timezone-aware")
    return timestamp.astimezone(UTC)


def detect_liquidity_sweeps(
    candles: list[Candle],
    levels: tuple[LiquidityLevel, ...],
) -> tuple[LiquiditySweep, ...]:
    """Detect penetration of a liquidity level followed by rejection.

    Buy-side liquidity is swept when a completed candle trades above the level
    and closes back below it. Sell-side liquidity is swept when a completed
    candle trades below the level and closes back above it.

    A close through the level is a breakout, not a sweep.
    """
    ordered = sorted(
        (candle for candle in candles if candle.is_complete),
        key=lambda candle: candle.timestamp,
    )
    result: list[LiquiditySweep] = []

    for candle in ordered:
        candle_time = _utc(candle.timestamp)
        candidates = [
            level
            for level in levels
            if level.instrument == candle.instrument
            and level.period_end <= candle_time
        ]

        for level in candidates:
            if level.side == "BUY_SIDE":
                swept = candle.high > level.price and candle.close < level.price
                direction = "BEARISH"
                sweep_price = candle.high
            else:
                swept = candle.low < level.price and candle.close > level.price
                direction = "BULLISH"
                sweep_price = candle.low

            if swept:
                result.append(
                    LiquiditySweep(
                        instrument=candle.instrument,
                        timeframe=candle.timeframe,
                        timestamp=candle.timestamp,
                        direction=direction,
                        level=level,
                        sweep_price=sweep_price,
                        close_price=candle.close,
                    )
                )

    return tuple(
        sorted(
            result,
            key=lambda sweep: (_utc(sweep.timestamp), sweep.level.price, sweep.level.kind),
        )
    )
