from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.execution.mt5_market_data import MetaTrader5MarketDataProvider


class FakeMT5:
    TIMEFRAME_5M = 5

    def __init__(self):
        self.visible = False
        self.selected = []
        self.shutdown_called = False

    def initialize(self, **kwargs):
        return True

    def shutdown(self):
        self.shutdown_called = True

    def symbol_info(self, symbol):
        return SimpleNamespace(visible=self.visible)

    def symbol_select(self, symbol, enabled):
        self.selected.append((symbol, enabled))
        self.visible = enabled
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(
            bid=2350.10,
            ask=2350.30,
            time=1_800_000_000,
            time_msc=1_800_000_000_000,
        )

    def copy_rates_from_pos(self, symbol, timeframe, start_pos, limit):
        assert start_pos == 1
        return [
            {
                "time": 1_800_000_000,
                "open": 2350.0,
                "high": 2351.0,
                "low": 2349.0,
                "close": 2350.5,
                "tick_volume": 42,
            }
        ]

    def last_error(self):
        return (0, "ok")


def test_provider_requires_connection():
    provider = MetaTrader5MarketDataProvider(FakeMT5())
    with pytest.raises(RuntimeError, match="not connected"):
        provider.get_quote("XAUUSDmicro")


def test_quote_selects_symbol_and_returns_decimal_prices():
    mt5 = FakeMT5()
    provider = MetaTrader5MarketDataProvider(mt5)
    provider.connect()

    quote = provider.get_quote("XAUUSDmicro")

    assert quote.instrument == "XAUUSDmicro"
    assert str(quote.bid) == "2350.1"
    assert str(quote.ask) == "2350.3"
    assert str(quote.mid) == "2350.2"
    assert mt5.selected == [("XAUUSDmicro", True)]


def test_candle_fetch_excludes_forming_bar_and_maps_data():
    mt5 = FakeMT5()
    provider = MetaTrader5MarketDataProvider(mt5)
    provider.connect()

    candles = provider.get_candles("XAUUSDmicro", "5M", limit=10)

    assert len(candles) == 1
    assert candles[0].instrument == "XAUUSDmicro"
    assert candles[0].timeframe == "5M"
    assert str(candles[0].close) == "2350.5"
    assert candles[0].source == "metatrader5"


def test_close_shuts_down_connected_terminal():
    mt5 = FakeMT5()
    provider = MetaTrader5MarketDataProvider(mt5)
    provider.connect()
    provider.close()

    assert mt5.shutdown_called
    with pytest.raises(RuntimeError, match="not connected"):
        provider.get_quote("XAUUSDmicro")


def test_rejects_naive_datetime():
    provider = MetaTrader5MarketDataProvider(FakeMT5())
    provider.connect()

    with pytest.raises(ValueError, match="timezone-aware"):
        provider.get_candles(
            "XAUUSDmicro",
            "5M",
            start=datetime(2026, 1, 1),
        )
