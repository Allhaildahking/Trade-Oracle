"""Collect a reusable historical dataset from a connected MT5 terminal."""

from __future__ import annotations

import argparse
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from app.backtesting.dataset_io import save_historical_dataset
from app.backtesting.mt5_dataset import collect_mt5_historical_dataset
from app.execution.mt5_market_data import MetaTrader5MarketDataProvider


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Use ISO 8601 with an explicit UTC offset, e.g. 2026-01-01T00:00:00+00:00"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Exact broker symbol, e.g. XAUUSDmicro")
    parser.add_argument("--start", required=True, type=_parse_datetime)
    parser.add_argument("--end", required=True, type=_parse_datetime)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-days", type=int, default=1)
    parser.add_argument("--min-spread-coverage", type=Decimal, default=Decimal("95"))
    parser.add_argument("--terminal-path", help="Optional path to terminal64.exe")
    args = parser.parse_args()

    provider = MetaTrader5MarketDataProvider()
    try:
        provider.connect(args.terminal_path)
        dataset = collect_mt5_historical_dataset(
            provider,
            instrument=args.symbol,
            start=args.start,
            end=args.end,
            chunk_days=args.chunk_days,
            minimum_spread_coverage_percent=args.min_spread_coverage,
        )
        destination = save_historical_dataset(dataset, args.output)
        print(f"Saved dataset: {destination}")
        print(f"Symbol: {dataset.instrument}")
        print(f"Symbol tick size: {dataset.symbol_spec.trade_tick_size}")
        print(f"5M spread coverage: {dataset.quality.five_minute_spread_coverage_percent:.2f}%")
        for timeframe, count in dataset.quality.candle_counts:
            print(f"{timeframe}: {count} completed candles")
        print("Historical quote snapshots are bar-level, not tick-by-tick fills.")
        return 0
    finally:
        provider.close()


if __name__ == "__main__":
    raise SystemExit(main())
