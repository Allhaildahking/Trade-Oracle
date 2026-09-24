"""Safe ingestion pipeline: fetch -> validate -> persist."""

from __future__ import annotations

from datetime import timedelta

from app.data.base import MarketDataProvider
from app.data.repository import CandleRepository
from app.data.validation import assert_valid_candles
from app.models.market import Candle, Timeframe

EXPECTED_INTERVALS: dict[Timeframe, timedelta] = {
    "4H": timedelta(hours=4),
    "1H": timedelta(hours=1),
    "15M": timedelta(minutes=15),
    "5M": timedelta(minutes=5),
}


def ingest_candles(
    provider: MarketDataProvider,
    repository: CandleRepository,
    instrument: str,
    timeframe: Timeframe,
    *,
    limit: int = 500,
) -> list[Candle]:
    candles = provider.get_candles(instrument, timeframe, limit=limit)
    assert_valid_candles(candles, expected_interval=EXPECTED_INTERVALS[timeframe])
    repository.upsert(candles)
    return candles
