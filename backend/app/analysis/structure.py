"""Deterministic swing, BOS, and CHoCH detection."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.models.market import Candle
from app.models.structure import StructureEvent, StructureSnapshot, SwingPoint


def detect_swings(
    candles: list[Candle],
    *,
    left: int = 2,
    right: int = 2,
) -> tuple[SwingPoint, ...]:
    """Detect confirmed local highs and lows using a symmetric window."""

    if left < 1 or right < 1:
        raise ValueError("left and right must be positive")

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    swings: list[SwingPoint] = []

    for index in range(left, len(ordered) - right):
        candle = ordered[index]
        window = ordered[index - left : index + right + 1]

        is_high = candle.high >= max(item.high for item in window)
        is_low = candle.low <= min(item.low for item in window)

        if is_high:
            swings.append(
                SwingPoint(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    price=candle.high,
                    kind="HIGH",
                    index=index,
                )
            )
        if is_low:
            swings.append(
                SwingPoint(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    price=candle.low,
                    kind="LOW",
                    index=index,
                )
            )

    return tuple(sorted(swings, key=lambda swing: (swing.index, swing.kind)))


def _prior_trend(swings: list[SwingPoint]) -> str | None:
    highs = [swing for swing in swings if swing.kind == "HIGH"]
    lows = [swing for swing in swings if swing.kind == "LOW"]

    if len(highs) >= 2 and len(lows) >= 2:
        higher_high = highs[-1].price > highs[-2].price
        higher_low = lows[-1].price > lows[-2].price
        lower_high = highs[-1].price < highs[-2].price
        lower_low = lows[-1].price < lows[-2].price

        if higher_high and higher_low:
            return "BULLISH"
        if lower_high and lower_low:
            return "BEARISH"

    return None


def detect_structure(
    candles: list[Candle],
    swings: tuple[SwingPoint, ...] | None = None,
) -> StructureSnapshot:
    """Detect close-confirmed BOS and CHoCH events from confirmed swings.

    A swing is considered broken only when a candle closes beyond its price.
    Each swing can generate at most one break event.
    """

    ordered = sorted(candles, key=lambda candle: candle.timestamp)
    detected_swings = swings if swings is not None else detect_swings(ordered)
    swings_by_index: dict[int, list[SwingPoint]] = defaultdict(list)

    for swing in detected_swings:
        swings_by_index[swing.index].append(swing)

    available: list[SwingPoint] = []
    broken: set[tuple[int, str]] = set()
    events: list[StructureEvent] = []

    for index, candle in enumerate(ordered):
        available.extend(swings_by_index.get(index, []))
        candidates = [
            swing
            for swing in available
            if (swing.index, swing.kind) not in broken and swing.index < index
        ]

        if not candidates:
            continue

        prior_trend = _prior_trend([swing for swing in available if swing.index < index])

        high_breaks = [
            swing for swing in candidates if candle.close > swing.price and swing.kind == "HIGH"
        ]
        low_breaks = [
            swing for swing in candidates if candle.close < swing.price and swing.kind == "LOW"
        ]

        if high_breaks:
            swing = max(high_breaks, key=lambda item: item.index)
            direction = "BULLISH"
            kind = "CHoCH" if prior_trend == "BEARISH" else "BOS"
            events.append(
                StructureEvent(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    price=candle.close,
                    kind=kind,
                    direction=direction,
                    broken_swing=swing,
                )
            )
            broken.add((swing.index, swing.kind))

        if low_breaks:
            swing = max(low_breaks, key=lambda item: item.index)
            direction = "BEARISH"
            kind = "CHoCH" if prior_trend == "BULLISH" else "BOS"
            events.append(
                StructureEvent(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    price=candle.close,
                    kind=kind,
                    direction=direction,
                    broken_swing=swing,
                )
            )
            broken.add((swing.index, swing.kind))

    return StructureSnapshot(
        swings=detected_swings,
        events=tuple(events),
    )
