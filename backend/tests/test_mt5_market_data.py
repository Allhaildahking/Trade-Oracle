from datetime import datetime
from decimal import Decimal
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
        return SimpleNamespace(
            visible=self.visible,
            trade_tick_size=0.01,
            trade_tick_value_loss=0.01,
            trade_tick_value=0.01,
            volume_min=0.1,
            volume_max=100.0,
            volume_step=0.1,
            trade_contract_size=1.0,
        )

    def symbol_select(self, symbol, enabled):
        self.selected.append((symbol, enabled))
        self.visible = enabled
        return True

    def account_info(self):
        return SimpleNamespace(equity=30.0)

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


def test_reads_account_equity_from_terminal():
    provider = MetaTrader5MarketDataProvider(FakeMT5())
    provider.connect()

    assert provider.get_account_equity() == Decimal("30.0")


def test_symbol_spec_reads_live_broker_constraints():
    mt5 = FakeMT5()
    provider = MetaTrader5MarketDataProvider(mt5)
    provider.connect()

    spec = provider.get_symbol_spec("XAUUSDmicro")

    assert spec.instrument == "XAUUSDmicro"
    assert spec.trade_tick_size == Decimal("0.01")
    assert spec.trade_tick_value_loss == Decimal("0.01")
    assert spec.volume_min == Decimal("0.1")
    assert spec.volume_step == Decimal("0.1")
    assert spec.contract_size == Decimal("1.0")


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
