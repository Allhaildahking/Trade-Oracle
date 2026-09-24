"""Provider contracts. Analysis code depends on these interfaces, not vendors."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.models.fundamental import EconomicEvent, NewsItem
from app.models.market import Candle, Quote, Timeframe


class MarketDataProvider(Protocol):
    name: str

    def get_candles(
        self,
        instrument: str,
        timeframe: Timeframe,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 500,
    ) -> list[Candle]:
        ...

    def get_quote(self, instrument: str) -> Quote:
        ...


class EconomicCalendarProvider(Protocol):
    name: str

    def get_events(
        self,
        *,
        countries: tuple[str, ...],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[EconomicEvent]:
        ...


class NewsProvider(Protocol):
    name: str

    def get_news(
        self,
        *,
        currencies: tuple[str, ...] = (),
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItem]:
        ...
