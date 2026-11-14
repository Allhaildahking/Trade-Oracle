"""Chunked historical dataset collection and quality gates for MT5 backtests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol

from app.models.market import Candle, Timeframe
from app.models.symbol import SymbolSpec

_TIMEFRAME_MINUTES: dict[Timeframe, int] = {
    "4H": 240,
    "1H": 60,
    "15M": 15,
    "5M": 5,
}
_TIMEFRAMES: tuple[Timeframe, ...] = ("4H", "1H", "15M", "5M")


class HistoricalMT5Provider(Protocol):
    def get_symbol_spec(self, instrument: str) -> SymbolSpec: ...

    def get_candles_with_spread(
        self,
        instrument: str,
        timeframe: Timeframe,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]: ...


@dataclass(frozen=True, slots=True)
class DatasetQuality:
    candle_counts: tuple[tuple[str, int], ...]
    five_minute_spread_coverage_percent: Decimal
    missing_five_minute_spreads: int
    first_five_minute_bar: datetime
    last_five_minute_bar: datetime


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    instrument: str
    start: datetime
    end: datetime
    symbol_spec: SymbolSpec
    candles: Mapping[str, tuple[Candle, ...]]
    quality: DatasetQuality


def collect_mt5_historical_dataset(
    provider: HistoricalMT5Provider,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
    chunk_days: int = 1,
    minimum_spread_coverage_percent: Decimal = Decimal("95"),
) -> HistoricalDataset:
    """Collect completed 4H/1H/15M/5M candles and historical quote snapshots.

    The provider is queried in small time windows to avoid MT5 history/tick
    request limits. A dataset is rejected if any timeframe is empty or if
    5-minute spread coverage is below the configured quality threshold.
    """
    if not instrument.strip():
        raise ValueError("instrument must not be blank")
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("start and end must be timezone-aware")
    if end <= start:
        raise ValueError("end must be later than start")
    if chunk_days < 1:
        raise ValueError("chunk_days must be at least 1")
    if not Decimal("0") <= minimum_spread_coverage_percent <= Decimal("100"):
        raise ValueError("minimum spread coverage must be between 0 and 100")

    symbol_spec = provider.get_symbol_spec(instrument)
    if symbol_spec.instrument != instrument:
        raise ValueError("broker symbol specification does not match requested instrument")

    collected: dict[Timeframe, dict[datetime, Candle]] = {
        timeframe: {} for timeframe in _TIMEFRAMES
    }
    cursor = start
    chunk = timedelta(days=chunk_days)
    while cursor < end:
        chunk_end = min(cursor + chunk, end)
        for timeframe in _TIMEFRAMES:
            rows = provider.get_candles_with_spread(
                instrument,
                timeframe,
                start=cursor,
                end=chunk_end,
                limit=1_000_000,
            )
            duration = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])
            for candle in rows:
                if candle.instrument != instrument or candle.timeframe != timeframe:
                    raise ValueError("provider returned a candle for the wrong symbol/timeframe")
                if candle.timestamp.tzinfo is None:
                    raise ValueError("provider returned a candle with a naive timestamp")
                if candle.timestamp < start or candle.timestamp + duration > end:
                    continue
                if not candle.is_complete:
                    continue
                existing = collected[timeframe].get(candle.timestamp)
                if existing is not None:
                    same_market_bar = (
                        existing.instrument == candle.instrument
                        and existing.timeframe == candle.timeframe
                        and existing.timestamp == candle.timestamp
                        and existing.open == candle.open
                        and existing.high == candle.high
                        and existing.low == candle.low
                        and existing.close == candle.close
                        and existing.volume == candle.volume
                    )
                    if not same_market_bar:
                        raise ValueError(
                            f"conflicting duplicate {timeframe} candle at "
                            f"{candle.timestamp.isoformat()}"
                        )

                    existing_has_spread = (
                        existing.bid is not None
                        and existing.ask is not None
                        and existing.bid > 0
                        and existing.ask >= existing.bid
                    )
                    candle_has_spread = (
                        candle.bid is not None
                        and candle.ask is not None
                        and candle.bid > 0
                        and candle.ask >= candle.bid
                    )
                    if not existing_has_spread and candle_has_spread:
                        collected[timeframe][candle.timestamp] = replace(
                            existing, bid=candle.bid, ask=candle.ask
                        )
                    continue

                collected[timeframe][candle.timestamp] = candle
        cursor = chunk_end

    for timeframe, rows in collected.items():
        if not rows:
            raise ValueError(f"no completed historical {timeframe} candles returned")

    ordered = {
        timeframe: tuple(sorted(rows.values(), key=lambda candle: candle.timestamp))
        for timeframe, rows in collected.items()
    }
    five_minute = ordered["5M"]
    missing_spreads = sum(
        candle.bid is None or candle.ask is None or candle.bid <= 0 or candle.ask < candle.bid
        for candle in five_minute
    )
    coverage = (
        Decimal(len(five_minute) - missing_spreads)
        / Decimal(len(five_minute))
        * Decimal("100")
    )
    if coverage < minimum_spread_coverage_percent:
        raise ValueError(
            "historical 5M spread coverage "
            f"{coverage:.2f}% is below required "
            f"{minimum_spread_coverage_percent:.2f}%"
        )

    quality = DatasetQuality(
        candle_counts=tuple((timeframe, len(ordered[timeframe])) for timeframe in _TIMEFRAMES),
        five_minute_spread_coverage_percent=coverage,
        missing_five_minute_spreads=missing_spreads,
        first_five_minute_bar=five_minute[0].timestamp,
        last_five_minute_bar=five_minute[-1].timestamp,
    )
    return HistoricalDataset(
        instrument=instrument,
        start=start,
        end=end,
        symbol_spec=symbol_spec,
        candles=ordered,
        quality=quality,
    )
