"""Deterministic displacement detection."""

from __future__ import annotations

from decimal import Decimal

from app.models.market import Candle
from app.models.displacement import Displacement


def detect_displacements(
    candles: list[Candle],
    *,
    lookback: int = 10,
    body_multiplier: Decimal = Decimal("1.5"),
    close_threshold: Decimal = Decimal("0.70"),
) -> tuple[Displacement, ...]:
    """Detect completed candles with unusually large directional bodies.

    Displacement requires:
    - a non-zero candle range and body;
    - body >= body_multiplier * average body of prior candles;
    - bullish candles closing in the upper close_threshold of their range;
    - bearish candles closing in the lower close_threshold of their range.

    Only prior candles are used for the baseline, preventing look-ahead.
    """
    if lookback < 1:
        raise ValueError("lookback must be positive")
    if body_multiplier <= 0:
        raise ValueError("body_multiplier must be positive")
    if not Decimal("0.5") < close_threshold < Decimal("1"):
        raise ValueError("close_threshold must be between 0.5 and 1")

    ordered = sorted(
        (candle for candle in candles if candle.is_complete),
        key=lambda candle: candle.timestamp,
    )
    result: list[Displacement] = []

    for index, candle in enumerate(ordered):
        if index < lookback:
            continue

        candle_range = candle.high - candle.low
        body = abs(candle.close - candle.open)
        if candle_range <= 0 or body <= 0:
            continue

        baseline = ordered[max(0, index - lookback) : index]
        body_values = [abs(item.close - item.open) for item in baseline]
        average_body = sum(body_values, Decimal("0")) / Decimal(len(body_values))

        if average_body <= 0 or body < body_multiplier * average_body:
            continue

        close_location = (candle.close - candle.low) / candle_range
        if candle.close > candle.open:
            if close_location < close_threshold:
                continue
            direction = "BULLISH"
        elif candle.close < candle.open:
            if close_location > Decimal("1") - close_threshold:
                continue
            direction = "BEARISH"
        else:
            continue

        result.append(
            Displacement(
                instrument=candle.instrument,
                timeframe=candle.timeframe,
                timestamp=candle.timestamp,
                direction=direction,
                body=body,
                range=candle_range,
                body_ratio=body / candle_range,
                average_body=average_body,
                close_location=close_location,
            )
        )

    return tuple(result)
