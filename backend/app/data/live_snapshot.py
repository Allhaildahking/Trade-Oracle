"""Shared live-market evidence snapshot for one Oracle scan.

The snapshot is intentionally immutable. Providers are queried once per
instrument and the resulting evidence is reused by the pair analyses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.constants import TIMEFRAMES
from app.data.base import EconomicCalendarProvider, MarketDataProvider, NewsProvider
from app.models.fundamental import EconomicEvent, NewsItem
from app.models.market import Candle, Quote, Timeframe


@dataclass(frozen=True, slots=True)
class InstrumentSnapshot:
    instrument: str
    candles: dict[Timeframe, tuple[Candle, ...]]
    quote: Quote
    events: tuple[EconomicEvent, ...]
    news: tuple[NewsItem, ...]


@dataclass(frozen=True, slots=True)
class LiveMarketSnapshot:
    checked_at: datetime
    instruments: tuple[str, ...]
    markets: dict[str, InstrumentSnapshot]


class LiveMarketSnapshotBuilder:
    """Collect shared live evidence before deterministic Oracle analysis."""

    def __init__(
        self,
        *,
        market: MarketDataProvider,
        calendar: EconomicCalendarProvider,
        news: NewsProvider,
    ) -> None:
        self.market = market
        self.calendar = calendar
        self.news = news

    def build(
        self,
        instruments: tuple[str, ...],
        *,
        checked_at: datetime,
        candle_limit: int = 500,
    ) -> LiveMarketSnapshot:
        if checked_at.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")
        if not instruments:
            raise ValueError("instruments must not be empty")
        if len(set(instruments)) != len(instruments):
            raise ValueError("instruments must be unique")

        markets: dict[str, InstrumentSnapshot] = {}
        for instrument in instruments:
            currencies = _instrument_currencies(instrument)
            countries = tuple(
                _CURRENCY_COUNTRIES[currency]
                for currency in currencies
                if currency in _CURRENCY_COUNTRIES
            )
            events = tuple(
                self.calendar.get_events(
                    countries=countries,
                    start=checked_at - _EVENT_LOOKBACK,
                    end=checked_at + _EVENT_LOOKAHEAD,
                )
            )
            news = tuple(
                self.news.get_news(
                    currencies=currencies,
                    start=checked_at - _NEWS_LOOKBACK,
                    end=checked_at,
                    limit=100,
                )
            )
            candles = {
                timeframe: tuple(
                    self.market.get_candles(
                        instrument,
                        timeframe,
                        limit=candle_limit,
                    )
                )
                for timeframe in TIMEFRAMES
            }
            markets[instrument] = InstrumentSnapshot(
                instrument=instrument,
                candles=candles,
                quote=self.market.get_quote(instrument),
                events=events,
                news=news,
            )

        return LiveMarketSnapshot(
            checked_at=checked_at,
            instruments=instruments,
            markets=markets,
        )


_EVENT_LOOKBACK = __import__("datetime").timedelta(minutes=30)
_EVENT_LOOKAHEAD = __import__("datetime").timedelta(minutes=30)
_NEWS_LOOKBACK = __import__("datetime").timedelta(days=7)


_CURRENCY_COUNTRIES = {
    "EUR": "euro area",
    "GBP": "united kingdom",
    "USD": "united states",
    "JPY": "japan",
    "CHF": "switzerland",
    "CAD": "canada",
    "AUD": "australia",
    "NZD": "new zealand",
}


def _instrument_currencies(instrument: str) -> tuple[str, str]:
    pair = instrument.upper()
    if len(pair) != 6 or not pair.isalpha():
        raise ValueError("instrument must be a six-letter currency symbol")
    return pair[:3], pair[3:]
