"""Storage contracts.

The first implementation is intentionally in-memory/test-friendly. PostgreSQL
can implement these protocols later without changing analysis code.
"""

from __future__ import annotations

from typing import Protocol

from app.models.market import Candle


class CandleRepository(Protocol):
    def upsert(self, candles: list[Candle]) -> int:
        ...

    def get(self, instrument: str, timeframe: str, limit: int = 500) -> list[Candle]:
        ...


class InMemoryCandleRepository:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[object, Candle]] = {}

    def upsert(self, candles: list[Candle]) -> int:
        inserted = 0
        for candle in candles:
            key = (candle.instrument, candle.timeframe)
            bucket = self._rows.setdefault(key, {})
            if candle.timestamp not in bucket:
                inserted += 1
            bucket[candle.timestamp] = candle
        return inserted

    def get(self, instrument: str, timeframe: str, limit: int = 500) -> list[Candle]:
        bucket = self._rows.get((instrument, timeframe), {})
        return sorted(bucket.values(), key=lambda candle: candle.timestamp)[-limit:]
