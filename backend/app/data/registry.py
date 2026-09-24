"""Provider registry. Keeps vendor wiring out of analysis code."""

from __future__ import annotations

from app.data.alpha_vantage import AlphaVantageNewsProvider
from app.data.base import EconomicCalendarProvider, MarketDataProvider, NewsProvider
from app.data.trading_economics import TradingEconomicsProvider
from app.data.twelve_data import TwelveDataProvider


def build_market_provider(api_key: str | None = None) -> MarketDataProvider:
    return TwelveDataProvider(api_key)


def build_calendar_provider(api_key: str | None = None) -> EconomicCalendarProvider:
    return TradingEconomicsProvider(api_key)


def build_news_provider(api_key: str | None = None) -> NewsProvider:
    return AlphaVantageNewsProvider(api_key)
