"""Deterministic liquidity mapping from completed candles.

All period boundaries are interpreted in UTC. Session definitions are explicit
and can be changed centrally without changing the domain model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.market import Candle
from app.models.liquidity import LiquidityLevel

_SESSION_WINDOWS = {
    "ASIA": (0, 8),
    "LONDON": (8, 13),
    "NEW_YORK": (13, 21),
}


def _ordered(candles: list[Candle]) -> list[Candle]:
    return sorted(
        (candle for candle in candles if candle.is_complete),
        key=lambda candle: candle.timestamp,
    )


def _utc(timestamp: datetime) -> datetime:
    if timestamp.tzinfo is None:
        raise ValueError("candle timestamps must be timezone-aware")
    return timestamp.astimezone(UTC)


def _day_start(timestamp: datetime) -> datetime:
    timestamp = _utc(timestamp)
    return timestamp.replace(hour=0, minute=0, second=0, microsecond=0)


def _week_start(timestamp: datetime) -> datetime:
    day = _day_start(timestamp)
    return day - timedelta(days=day.weekday())


def _period_high_low(candles: list[Candle], start: datetime, end: datetime):
    scoped = [c for c in candles if start <= _utc(c.timestamp) < end]
    if not scoped:
        return None
    return max(c.high for c in scoped), min(c.low for c in scoped)


def map_liquidity(candles: list[Candle]) -> tuple[LiquidityLevel, ...]:
    """Map previous-day, previous-week, and UTC session liquidity levels."""
    ordered = _ordered(candles)
    if not ordered:
        return ()

    result: list[LiquidityLevel] = []
    seen: set[tuple[str, str, str, datetime]] = set()

    for candle in ordered:
        timestamp = _utc(candle.timestamp)
        day = _day_start(timestamp)
        previous_day = day - timedelta(days=1)
        previous_week = _week_start(timestamp) - timedelta(days=7)

        day_periods = [
            ("PREVIOUS_DAY_HIGH", "BUY_SIDE", previous_day, day),
            ("PREVIOUS_DAY_LOW", "SELL_SIDE", previous_day, day),
        ]
        week_end = _week_start(timestamp)
        week_periods = [
            ("PREVIOUS_WEEK_HIGH", "BUY_SIDE", previous_week, week_end),
            ("PREVIOUS_WEEK_LOW", "SELL_SIDE", previous_week, week_end),
        ]

        for kind, side, start, end in day_periods + week_periods:
            key = (candle.instrument, kind, str(start), timestamp)
            if key in seen:
                continue
            values = _period_high_low(ordered, start, end)
            if values is None:
                continue
            high, low = values
            price = high if kind.endswith("HIGH") else low
            result.append(
                LiquidityLevel(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    kind=kind,
                    side=side,
                    price=price,
                    period_start=start,
                    period_end=end,
                    label=kind.replace("_", " "),
                )
            )
            seen.add(key)

        for session, (start_hour, end_hour) in _SESSION_WINDOWS.items():
            session_start = day + timedelta(hours=start_hour)
            session_end = day + timedelta(hours=end_hour)
            if timestamp < session_end:
                continue
            values = _period_high_low(ordered, session_start, session_end)
            if values is None:
                continue
            high, low = values
            for kind, side, price in (
                ("SESSION_HIGH", "BUY_SIDE", high),
                ("SESSION_LOW", "SELL_SIDE", low),
            ):
                key = (candle.instrument, f"{kind}:{session}", str(session_start), timestamp)
                if key in seen:
                    continue
                result.append(
                    LiquidityLevel(
                        instrument=candle.instrument,
                        timeframe=candle.timeframe,
                        kind=kind,
                        side=side,
                        price=price,
                        period_start=session_start,
                        period_end=session_end,
                        label=f"{session} {kind.replace('_', ' ')}",
                        session=session,
                    )
                )
                seen.add(key)

    return tuple(
        sorted(result, key=lambda level: (level.period_end, level.price, level.kind))
    )
