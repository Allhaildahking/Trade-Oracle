"""Twelve Data market-data adapter.

Twelve Data supports historical/intraday time series and WebSocket streaming.
This adapter handles REST first; streaming can be added without changing the
analysis layer.
"""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from decimal import Decimal
import os
import time

from app.data.base import MarketDataProvider
from app.data.http import ProviderError, get_json
from app.models.market import Candle, Quote, Timeframe

TIMEFRAME_MAP: dict[Timeframe, str] = {
    "4H": "4h",
    "1H": "1h",
    "15M": "15min",
    "5M": "5min",
}

INSTRUMENT_MAP = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "USDCAD": "USD/CAD",
    "AUDUSD": "AUD/USD",
    "NZDUSD": "NZD/USD",
    "XAUUSD": "XAU/USD",
}

_CREDIT_LIMIT = 8
_CREDIT_WINDOW_SECONDS = 60.0


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


class TwelveDataProvider(MarketDataProvider):
    name = "twelve_data"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY", "")
        if not self.api_key:
            raise ProviderError("TWELVE_DATA_API_KEY is not configured.")
        self._credit_times: deque[float] = deque()

    def _wait_for_credit(self) -> None:
        now = time.monotonic()
        cutoff = now - _CREDIT_WINDOW_SECONDS
        while self._credit_times and self._credit_times[0] <= cutoff:
            self._credit_times.popleft()

        if len(self._credit_times) >= _CREDIT_LIMIT:
            wait_for = _CREDIT_WINDOW_SECONDS - (now - self._credit_times[0])
            time.sleep(max(wait_for, 0.0))
            self._wait_for_credit()
            return

        self._credit_times.append(now)

    def get_candles(
        self,
        instrument: str,
        timeframe: Timeframe,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        if instrument not in INSTRUMENT_MAP:
            raise ValueError(f"Unsupported instrument: {instrument}")
        params: dict[str, str | int] = {
            "symbol": INSTRUMENT_MAP[instrument],
            "interval": TIMEFRAME_MAP[timeframe],
            "outputsize": min(limit, 5000),
            "timezone": "UTC",
            "apikey": self.api_key,
        }
        if start:
            params["start_date"] = start.astimezone(UTC).isoformat()
        if end:
            params["end_date"] = end.astimezone(UTC).isoformat()

        self._wait_for_credit()
        payload = get_json("https://api.twelvedata.com/time_series", params)
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            raise ProviderError(f"Unexpected Twelve Data response: {payload}")

        values = payload.get("values", [])
        candles: list[Candle] = []
        for row in values:
            candles.append(
                Candle(
                    instrument=instrument,
                    timeframe=timeframe,
                    timestamp=_parse_datetime(str(row["datetime"])),
                    open=_decimal(row["open"]),
                    high=_decimal(row["high"]),
                    low=_decimal(row["low"]),
                    close=_decimal(row["close"]),
                    volume=_decimal(row["volume"]) if row.get("volume") is not None else None,
                    source=self.name,
                )
            )
        return sorted(candles, key=lambda candle: candle.timestamp)

    def get_quote(self, instrument: str) -> Quote:
        if instrument not in INSTRUMENT_MAP:
            raise ValueError(f"Unsupported instrument: {instrument}")
        self._wait_for_credit()
        payload = get_json(
            "https://api.twelvedata.com/quote",
            {"symbol": INSTRUMENT_MAP[instrument], "apikey": self.api_key},
        )
        if not isinstance(payload, dict) or "close" not in payload:
            raise ProviderError(f"Unexpected Twelve Data quote response: {payload}")

        close = _decimal(payload["close"])
        return Quote(
            instrument=instrument,
            timestamp=datetime.now(UTC),
            bid=None,
            ask=None,
            mid=close,
            source=self.name,
        )
