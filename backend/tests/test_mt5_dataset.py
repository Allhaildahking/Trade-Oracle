# ruff: noqa: I001
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.backtesting.dataset_io import load_historical_dataset, save_historical_dataset
from app.backtesting.mt5_dataset import collect_mt5_historical_dataset
from app.models.market import Candle
from app.models.symbol import SymbolSpec


START = datetime(2026, 1, 5, tzinfo=UTC)


def _spec() -> SymbolSpec:
    return SymbolSpec(
        instrument="EURUSD",
        trade_tick_size=Decimal("0.0001"),
        trade_tick_value_loss=Decimal("1"),
        volume_min=Decimal("0.01"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.01"),
        contract_size=Decimal("100000"),
    )


class FakeHistoricalProvider:
    def __init__(self, *, missing_spread: bool = False):
        self.calls = []
        self.missing_spread = missing_spread

    def get_symbol_spec(self, instrument):
        assert instrument == "EURUSD"
        return _spec()

    def get_candles_with_spread(
        self, instrument, timeframe, *, start=None, end=None, limit=500
    ):
        self.calls.append((timeframe, start, end, limit))
        timestamp = start
        return [
            Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=timestamp,
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                bid=None if self.missing_spread and timeframe == "5M" else Decimal("1.1004"),
                ask=None if self.missing_spread and timeframe == "5M" else Decimal("1.1006"),
                source="fake_mt5",
                is_complete=True,
            )
        ]


def test_collects_all_timeframes_in_bounded_chunks_and_reports_quality():
    provider = FakeHistoricalProvider()
    dataset = collect_mt5_historical_dataset(
        provider,
        instrument="EURUSD",
        start=START,
        end=START + timedelta(days=2),
        chunk_days=1,
    )

    assert tuple(dataset.candles) == ("4H", "1H", "15M", "5M")
    assert all(len(rows) == 2 for rows in dataset.candles.values())
    assert dataset.quality.five_minute_spread_coverage_percent == Decimal("100")
    assert dataset.quality.missing_five_minute_spreads == 0
    assert len(provider.calls) == 8
    assert all(call[3] == 1_000_000 for call in provider.calls)


def test_rejects_dataset_when_historical_spread_coverage_is_too_low():
    provider = FakeHistoricalProvider(missing_spread=True)

    with pytest.raises(ValueError, match="spread coverage"):
        collect_mt5_historical_dataset(
            provider,
            instrument="EURUSD",
            start=START,
            end=START + timedelta(days=1),
        )


def test_rejects_naive_or_reversed_date_ranges():
    provider = FakeHistoricalProvider()

    with pytest.raises(ValueError, match="timezone-aware"):
        collect_mt5_historical_dataset(
            provider,
            instrument="EURUSD",
            start=datetime(2026, 1, 5),
            end=START + timedelta(days=1),
        )

    with pytest.raises(ValueError, match="later than start"):
        collect_mt5_historical_dataset(
            provider,
            instrument="EURUSD",
            start=START + timedelta(days=1),
            end=START,
        )



def test_saved_dataset_round_trips_exact_decimal_values(tmp_path):
    provider = FakeHistoricalProvider()
    dataset = collect_mt5_historical_dataset(
        provider,
        instrument="EURUSD",
        start=START,
        end=START + timedelta(days=1),
    )

    path = save_historical_dataset(dataset, tmp_path / "history" / "eurusd.json")
    restored = load_historical_dataset(path)

    assert restored == dataset
    assert restored.symbol_spec.trade_tick_size == Decimal("0.0001")
    assert restored.candles["5M"][0].bid == Decimal("1.1004")


def test_saved_dataset_rejects_unknown_schema_version(tmp_path):
    path = tmp_path / "unknown.json"
    path.write_text('{"schema_version": 999}', encoding="utf-8")

    with pytest.raises(ValueError, match="schema version"):
        load_historical_dataset(path)


def test_merges_identical_boundary_candle_and_keeps_available_spread():
    provider = FakeHistoricalProvider()
    original = provider.get_candles_with_spread

    def overlapping_provider(instrument, timeframe, *, start=None, end=None, limit=500):
        rows = original(instrument, timeframe, start=start, end=end, limit=limit)
        if start == START + timedelta(days=1):
            rows[0] = Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=START,
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                bid=Decimal("1.1004"),
                ask=Decimal("1.1006"),
                source="fake_mt5",
                is_complete=True,
            )
        return rows

    provider.get_candles_with_spread = overlapping_provider
    dataset = collect_mt5_historical_dataset(
        provider,
        instrument="EURUSD",
        start=START,
        end=START + timedelta(days=2),
        chunk_days=1,
    )

    assert len(dataset.candles["4H"]) == 2
    assert dataset.candles["4H"][0].bid == Decimal("1.1004")
    assert dataset.candles["4H"][0].ask == Decimal("1.1006")


def test_still_rejects_duplicate_candles_with_different_ohlc():
    provider = FakeHistoricalProvider()
    original = provider.get_candles_with_spread

    def conflicting_provider(instrument, timeframe, *, start=None, end=None, limit=500):
        rows = original(instrument, timeframe, start=start, end=end, limit=limit)
        if start == START + timedelta(days=1):
            rows[0] = Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=START,
                open=Decimal("1.1000"),
                high=Decimal("1.1020"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
                bid=Decimal("1.1004"),
                ask=Decimal("1.1006"),
                source="fake_mt5",
                is_complete=True,
            )
        return rows

    provider.get_candles_with_spread = conflicting_provider
    with pytest.raises(ValueError, match="conflicting duplicate 4H candle"):
        collect_mt5_historical_dataset(
            provider,
            instrument="EURUSD",
            start=START,
            end=START + timedelta(days=2),
            chunk_days=1,
        )
