"""Deterministic break-and-retest detection."""

from __future__ import annotations

from decimal import Decimal

from app.models.break_retest import BreakRetest
from app.models.market import Candle


def detect_break_retests(
    candles: list[Candle],
    *,
    levels: tuple[Decimal, ...] = (),
    tolerance: Decimal = Decimal("0"),
    max_retest_bars: int = 3,
) -> tuple[BreakRetest, ...]:
    """Detect a close through a level followed by a successful retest.

    Bullish:
    1. A completed candle closes above the level.
    2. Within the next max_retest_bars, price revisits the level.
    3. The retest candle closes back above the level.

    Bearish is the inverse.

    Only completed candles are considered, and each level gets at most one
    detected retest from its first valid break.
    """
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    if max_retest_bars < 1:
        raise ValueError("max_retest_bars must be positive")

    ordered = sorted(
        (candle for candle in candles if candle.is_complete),
        key=lambda candle: candle.timestamp,
    )
    result: list[BreakRetest] = []

    for level in levels:
        for index, candle in enumerate(ordered):
            if candle.close > level:
                direction = "BULLISH"
                break_price = candle.close
                retest_end = min(len(ordered), index + max_retest_bars + 1)

                for retest in ordered[index + 1 : retest_end]:
                    touched = (
                        retest.low <= level + tolerance
                        and retest.high >= level - tolerance
                    )
                    if touched and retest.close > level:
                        result.append(
                            BreakRetest(
                                instrument=retest.instrument,
                                timeframe=retest.timeframe,
                                timestamp=retest.timestamp,
                                direction=direction,
                                level=level,
                                break_price=break_price,
                                retest_price=level,
                                close_price=retest.close,
                            )
                        )
                        break
                break

            if candle.close < level:
                direction = "BEARISH"
                break_price = candle.close
                retest_end = min(len(ordered), index + max_retest_bars + 1)

                for retest in ordered[index + 1 : retest_end]:
                    touched = (
                        retest.low <= level + tolerance
                        and retest.high >= level - tolerance
                    )
                    if touched and retest.close < level:
                        result.append(
                            BreakRetest(
                                instrument=retest.instrument,
                                timeframe=retest.timeframe,
                                timestamp=retest.timestamp,
                                direction=direction,
                                level=level,
                                break_price=break_price,
                                retest_price=level,
                                close_price=retest.close,
                            )
                        )
                        break
                break

    return tuple(sorted(result, key=lambda item: item.timestamp))
