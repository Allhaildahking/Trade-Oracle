"""Run a reproducible technical-only historical backtest from a saved MT5 dataset."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path

from app.backtesting.dataset_io import load_historical_dataset
from app.backtesting.engine import BacktestConfig, run_backtest
from app.backtesting.technical_adapter import build_technical_only_analyzer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--starting-equity", type=Decimal, default=Decimal("10"))
    parser.add_argument("--output", type=Path, default=Path("backtest-report.json"))
    parser.add_argument("--max-risk-per-trade", type=Decimal, default=Decimal("3.50"))
    parser.add_argument("--cash-risk-balance-threshold", type=Decimal, default=Decimal("15"))
    parser.add_argument("--risk-above-cash-threshold-percent", type=Decimal, default=Decimal("10"))
    parser.add_argument("--daily-loss-below-threshold", type=Decimal, default=Decimal("3"))
    parser.add_argument("--daily-loss-at-or-above-threshold", type=Decimal, default=Decimal("2"))
    parser.add_argument("--reduced-risk-balance-threshold", type=Decimal, default=Decimal("30"))
    parser.add_argument("--commission-per-lot-round-turn", type=Decimal, default=Decimal("0"))
    parser.add_argument("--slippage-ticks-per-side", type=Decimal, default=Decimal("0"))
    parser.add_argument("--broker-timezone", default="UTC")
    args = parser.parse_args()

    dataset = load_historical_dataset(args.dataset)
    analyzer = build_technical_only_analyzer(instrument=dataset.instrument)
    config = BacktestConfig(
        starting_equity=args.starting_equity,
        max_risk_per_trade_cash=args.max_risk_per_trade,
        cash_risk_balance_threshold=args.cash_risk_balance_threshold,
        risk_above_cash_threshold_percent=args.risk_above_cash_threshold_percent,
        daily_loss_below_threshold_percent=args.daily_loss_below_threshold,
        daily_loss_at_or_above_threshold_percent=args.daily_loss_at_or_above_threshold,
        reduced_risk_balance_threshold=args.reduced_risk_balance_threshold,
        commission_per_lot_round_turn=args.commission_per_lot_round_turn,
        slippage_ticks_per_side=args.slippage_ticks_per_side,
        broker_timezone=args.broker_timezone,
    )
    result = run_backtest(
        instrument=dataset.instrument,
        candles={timeframe: list(rows) for timeframe, rows in dataset.candles.items()},
        symbol_spec=dataset.symbol_spec,
        analyzer=analyzer,
        config=config,
    )

    report = {
        "report_type": "technical_only_diagnostic",
        "instrument": dataset.instrument,
        "dataset": {
            "start": dataset.start.isoformat(),
            "end": dataset.end.isoformat(),
            "candle_counts": dict(dataset.quality.candle_counts),
            "five_minute_spread_coverage_percent": str(
                dataset.quality.five_minute_spread_coverage_percent
            ),
            "missing_five_minute_spreads": dataset.quality.missing_five_minute_spreads,
        },
        "assumptions": {
            "starting_equity": str(config.starting_equity),
            "max_risk_per_trade_cash": str(config.max_risk_per_trade_cash),
            "cash_risk_balance_threshold": str(config.cash_risk_balance_threshold),
            "risk_above_cash_threshold_percent": str(config.risk_above_cash_threshold_percent),
            "daily_loss_below_threshold_percent": str(
                config.daily_loss_below_threshold_percent
            ),
            "daily_loss_at_or_above_threshold_percent": str(
                config.daily_loss_at_or_above_threshold_percent
            ),
            "reduced_risk_balance_threshold": str(
                config.reduced_risk_balance_threshold
            ),
            "commission_per_lot_round_turn": str(
                config.commission_per_lot_round_turn
            ),
            "slippage_ticks_per_side": str(config.slippage_ticks_per_side),
            "broker_timezone": config.broker_timezone,
            "spread_model": "one bid/ask snapshot per 5M candle; not tick-by-tick",
            "entry_model": "signal at completed 5M close; entry at next 5M open",
            "same_bar_stop_and_target": "stop loss assumed first",
            "fundamentals_and_economic_calendar": "excluded",
        },
        "results": asdict(result),
        "warnings": [
            "Technical-only diagnostic. It is not approved for live execution.",
            "Zero commission and zero slippage are assumptions unless explicitly configured.",
            "Historical 5M spread snapshots do not reproduce the tick-by-tick bid/ask path.",
            "Results do not establish future profitability or demo/live readiness.",
            *result.warnings,
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"Instrument: {result.instrument}")
    print(f"Trades: {result.trade_count} | Wins: {result.wins} | Losses: {result.losses}")
    print(f"Win rate: {result.win_rate_percent:.2f}%")
    print(f"Net return: {result.net_return_percent:.2f}%")
    print(f"Profit factor: {result.profit_factor if result.profit_factor is not None else 'N/A'}")
    print(f"Expectancy: {result.expectancy_r:.4f}R")
    print(f"Max drawdown: {result.max_drawdown_percent:.2f}%")
    print(f"Skipped signals: {result.skipped_signals}")
    print(f"Report: {args.output}")
    print("DIAGNOSTIC ONLY: technical-only; fundamentals/calendar excluded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
