"""Chronological, no-lookahead historical replay for the existing Oracle pipeline.

The engine deliberately accepts an injected analyzer. The caller is responsible
for building PairBias, calendar/news context and a historical quote using only
information available at the supplied as-of time. No live providers are called.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.execution.position_sizing import calculate_position_size
from app.models.market import Candle
from app.models.oracle import OracleAnalysis
from app.models.symbol import SymbolSpec

_TIMEFRAME_DURATION = {
    "4H": timedelta(hours=4),
    "1H": timedelta(hours=1),
    "15M": timedelta(minutes=15),
    "5M": timedelta(minutes=5),
}
_ZERO = Decimal("0")
_ONE_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    starting_equity: Decimal
    risk_below_threshold_percent: Decimal = Decimal("10")
    risk_at_or_above_threshold_percent: Decimal = Decimal("5")
    daily_loss_below_threshold_percent: Decimal = Decimal("20")
    daily_loss_at_or_above_threshold_percent: Decimal = Decimal("10")
    reduced_risk_balance_threshold: Decimal = Decimal("30")
    commission_per_lot_round_turn: Decimal = _ZERO
    slippage_ticks_per_side: Decimal = Decimal("0")
    max_open_positions: int = 1
    broker_timezone: str = "UTC"

    def __post_init__(self) -> None:
        if self.starting_equity <= 0:
            raise ValueError("starting_equity must be positive")
        if not (
            _ZERO < self.risk_below_threshold_percent <= Decimal("10")
            and _ZERO < self.risk_at_or_above_threshold_percent <= Decimal("10")
        ):
            raise ValueError("risk percentages must be in (0, 10]")
        if not (
            _ZERO < self.daily_loss_below_threshold_percent <= Decimal("20")
            and _ZERO < self.daily_loss_at_or_above_threshold_percent <= Decimal("20")
        ):
            raise ValueError("daily loss percentages must be in (0, 20]")
        if self.reduced_risk_balance_threshold <= 0:
            raise ValueError("reduced_risk_balance_threshold must be positive")
        if self.commission_per_lot_round_turn < 0 or self.slippage_ticks_per_side < 0:
            raise ValueError("cost assumptions must not be negative")
        if self.max_open_positions != 1:
            raise ValueError("V1 backtester supports exactly one open position")
        ZoneInfo(self.broker_timezone)


@dataclass(frozen=True, slots=True)
class BacktestTrade:
    instrument: str
    direction: str
    signal_time: datetime
    entry_time: datetime
    exit_time: datetime
    entry: Decimal
    exit: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    volume: Decimal
    gross_pnl: Decimal
    commission: Decimal
    net_pnl: Decimal
    result: str
    r_multiple: Decimal


@dataclass(frozen=True, slots=True)
class BacktestMonth:
    year_month: str
    trade_count: int
    wins: int
    losses: int
    net_pnl: Decimal
    win_rate_percent: Decimal


@dataclass(frozen=True, slots=True)
class BacktestResult:
    instrument: str
    starting_equity: Decimal
    ending_equity: Decimal
    net_return_percent: Decimal
    trade_count: int
    wins: int
    losses: int
    win_rate_percent: Decimal
    gross_profit: Decimal
    gross_loss: Decimal
    average_win: Decimal
    average_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    average_rr: Decimal
    monthly_breakdown: tuple[BacktestMonth, ...]
    profit_factor: Decimal | None
    expectancy_r: Decimal
    max_drawdown_percent: Decimal
    max_daily_drawdown_percent: Decimal
    max_consecutive_losses: int
    skipped_signals: int
    trades: tuple[BacktestTrade, ...]
    warnings: tuple[str, ...]


Analyzer = Callable[[datetime, Mapping[str, list[Candle]]], OracleAnalysis]


@dataclass(slots=True)
class _OpenTrade:
    instrument: str
    direction: str
    signal_time: datetime
    entry_time: datetime
    entry: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    volume: Decimal
    risk_cash: Decimal
    commission: Decimal


def run_backtest(
    *,
    instrument: str,
    candles: Mapping[str, list[Candle]],
    symbol_spec: SymbolSpec,
    analyzer: Analyzer,
    config: BacktestConfig,
) -> BacktestResult:
    """Replay completed 5M bars in time order using only already-closed data.

    Analyzer is called at each 5M close and receives only candles whose close
    time is <= that timestamp. Signals enter no earlier than the next 5M open.
    If SL and TP are both touched in one bar, SL is assumed first. Missing
    bid/ask spread data blocks entry rather than silently assuming zero spread.
    """
    if symbol_spec.instrument != instrument:
        raise ValueError("symbol_spec instrument must match requested instrument")
    if not candles.get("5M"):
        raise ValueError("5M candles are required")
    for timeframe, rows in candles.items():
        if timeframe not in _TIMEFRAME_DURATION:
            raise ValueError(f"unsupported timeframe: {timeframe}")
        if any(row.instrument != instrument or row.timeframe != timeframe for row in rows):
            raise ValueError(f"{timeframe} candle instrument/timeframe mismatch")
        if any(row.timestamp.tzinfo is None for row in rows):
            raise ValueError(f"{timeframe} candle timestamps must be timezone-aware")
        if any(not row.is_complete for row in rows):
            raise ValueError(f"{timeframe} input contains incomplete candles")
        ordered = sorted(rows, key=lambda row: row.timestamp)
        if len({row.timestamp for row in ordered}) != len(ordered):
            raise ValueError(f"{timeframe} contains duplicate candle timestamps")
        candles = {**candles, timeframe: ordered}

    bars = candles["5M"]
    if len(bars) < 2:
        raise ValueError("at least two 5M candles are required")
    tz = ZoneInfo(config.broker_timezone)
    equity = config.starting_equity
    peak_equity = equity
    max_drawdown = _ZERO
    max_daily_drawdown = _ZERO
    daily_start: dict[date, Decimal] = {}
    daily_locked: set[date] = set()
    open_trade: _OpenTrade | None = None
    pending: tuple[OracleAnalysis, datetime] | None = None
    trades: list[BacktestTrade] = []
    warnings: list[str] = []
    skipped = 0
    consecutive_losses = 0
    max_consecutive_losses = 0

    for index, bar in enumerate(bars):
        bar_open = bar.timestamp
        bar_close = bar_open + _TIMEFRAME_DURATION["5M"]
        day = bar_close.astimezone(tz).date()
        daily_start.setdefault(day, equity)
        day_start_equity = daily_start[day]
        threshold_pct = (
            config.daily_loss_at_or_above_threshold_percent
            if day_start_equity >= config.reduced_risk_balance_threshold
            else config.daily_loss_below_threshold_percent
        )
        daily_limit = day_start_equity * threshold_pct / _ONE_HUNDRED
        day_realized_loss = max(_ZERO, day_start_equity - equity)
        if day_realized_loss >= daily_limit:
            daily_locked.add(day)

        # A pending signal from the previous close may enter at this bar's open.
        if pending is not None and open_trade is None:
            analysis, signal_time = pending
            pending = None
            trade = analysis.trade
            if day in daily_locked:
                skipped += 1
            elif (
                analysis.decision != "TRADE"
                or trade is None
                or trade.status != "VALID"
                or trade.entry is None
                or trade.stop_loss is None
                or trade.take_profit is None
                or trade.risk_reward is None
                or trade.risk_reward < Decimal("2.5")
                or analysis.risk is None
                or not analysis.risk.valid
                or analysis.risk.decision != "TRADE"
                or analysis.risk.expires_at is None
                or analysis.risk.expires_at <= bar_open
                or analysis.risk.checked_at > signal_time
            ):
                skipped += 1
            elif bar.bid is None or bar.ask is None or bar.ask < bar.bid:
                skipped += 1
                warnings.append(f"Skipped entry at {bar_open.isoformat()}: missing/invalid spread")
            else:
                risk_pct = (
                    config.risk_at_or_above_threshold_percent
                    if equity >= config.reduced_risk_balance_threshold
                    else config.risk_below_threshold_percent
                )
                half_spread = (bar.ask - bar.bid) / Decimal("2")
                slippage = config.slippage_ticks_per_side * symbol_spec.trade_tick_size
                fill = (
                    bar.open + half_spread + slippage
                    if trade.direction == "BUY"
                    else bar.open - half_spread - slippage
                )
                # Reject a gap that makes the original stop invalid.
                if (
                    (trade.direction == "BUY" and fill <= trade.stop_loss)
                    or (trade.direction == "SELL" and fill >= trade.stop_loss)
                ):
                    skipped += 1
                else:
                    exit_cost = half_spread + slippage
                    actual_risk = abs(fill - trade.stop_loss) + exit_cost
                    actual_reward = abs(trade.take_profit - fill) - exit_cost
                    if actual_risk <= 0 or actual_reward <= 0:
                        skipped += 1
                    elif actual_reward / actual_risk < Decimal("2.5"):
                        skipped += 1
                    else:
                        # Reserve for estimated spread/slippage on both sides.
                        sizing_stop = (
                            trade.stop_loss - exit_cost
                            if trade.direction == "BUY"
                            else trade.stop_loss + exit_cost
                        )
                        size = calculate_position_size(
                            equity=equity,
                            risk_percent=risk_pct,
                            direction=trade.direction,
                            entry=fill,
                            stop_loss=sizing_stop,
                            spec=symbol_spec,
                        )
                        if not size.accepted or size.volume is None:
                            skipped += 1
                        else:
                            risk_cash = (
                                actual_risk
                                / symbol_spec.trade_tick_size
                                * symbol_spec.trade_tick_value_loss
                                * size.volume
                            )
                            open_trade = _OpenTrade(
                                instrument=instrument,
                                direction=trade.direction,
                                signal_time=signal_time,
                                entry_time=bar_open,
                                entry=fill,
                                stop_loss=trade.stop_loss,
                                take_profit=trade.take_profit,
                                volume=size.volume,
                                risk_cash=risk_cash,
                                commission=config.commission_per_lot_round_turn * size.volume,
                            )

        # Resolve exits conservatively. Both touched means stop loss first.
        if open_trade is not None:
            position = open_trade
            hit_sl = (
                bar.low <= position.stop_loss
                if position.direction == "BUY"
                else bar.high >= position.stop_loss
            )
            hit_tp = (
                bar.high >= position.take_profit
                if position.direction == "BUY"
                else bar.low <= position.take_profit
            )
            exit_price: Decimal | None = None
            if hit_sl:
                exit_price = position.stop_loss
            elif hit_tp:
                exit_price = position.take_profit

            if exit_price is not None:
                if bar.bid is None or bar.ask is None or bar.ask < bar.bid:
                    skipped += 1
                    warnings.append(
                        f"Exit spread missing at {bar_close.isoformat()}; "
                        "position remains open for conservative later resolution"
                    )
                else:
                    half_spread = (bar.ask - bar.bid) / Decimal("2")
                    slippage = config.slippage_ticks_per_side * symbol_spec.trade_tick_size
                    fill = (
                        exit_price - half_spread - slippage
                        if position.direction == "BUY"
                        else exit_price + half_spread + slippage
                    )
                    sign = Decimal("1") if position.direction == "BUY" else Decimal("-1")
                    gross = (
                        (fill - position.entry)
                        / symbol_spec.trade_tick_size
                        * symbol_spec.trade_tick_value_loss
                        * position.volume
                        * sign
                    )
                    net = gross - position.commission
                    equity += net
                    trades.append(
                        BacktestTrade(
                            instrument=instrument,
                            direction=position.direction,
                            signal_time=position.signal_time,
                            entry_time=position.entry_time,
                            exit_time=bar_close,
                            entry=position.entry,
                            exit=fill,
                            stop_loss=position.stop_loss,
                            take_profit=position.take_profit,
                            volume=position.volume,
                            gross_pnl=gross,
                            commission=position.commission,
                            net_pnl=net,
                            result="WIN" if net > 0 else "LOSS",
                            r_multiple=(net / position.risk_cash)
                            if position.risk_cash > 0
                            else _ZERO,
                        )
                    )
                    consecutive_losses = consecutive_losses + 1 if net <= 0 else 0
                    max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                    open_trade = None

        peak_equity = max(peak_equity, equity)
        if peak_equity > 0:
            max_drawdown = max(max_drawdown, (peak_equity - equity) / peak_equity)
        daily_peak = max(day_start_equity, equity)
        if daily_peak > 0:
            max_daily_drawdown = max(
                max_daily_drawdown, (daily_peak - equity) / day_start_equity
            )

        # Analyze only after the current 5M candle is fully closed.
        if index < len(bars) - 1 and open_trade is None and pending is None:
            available = {
                timeframe: [
                    row
                    for row in rows
                    if row.timestamp + _TIMEFRAME_DURATION[timeframe] <= bar_close
                ]
                for timeframe, rows in candles.items()
            }
            if all(available.get(tf) for tf in ("4H", "1H", "15M", "5M")):
                analysis = analyzer(bar_close, available)
                if analysis.instrument != instrument:
                    raise ValueError("analyzer returned a different instrument")
                if analysis.decision == "TRADE":
                    pending = (analysis, bar_close)

    # Force-close any remaining position at the last available close, with costs.
    if open_trade is not None:
        last = bars[-1]
        if last.bid is not None and last.ask is not None and last.ask >= last.bid:
            position = open_trade
            half_spread = (last.ask - last.bid) / Decimal("2")
            slippage = config.slippage_ticks_per_side * symbol_spec.trade_tick_size
            fill = (
                last.close - half_spread - slippage
                if position.direction == "BUY"
                else last.close + half_spread + slippage
            )
            sign = Decimal("1") if position.direction == "BUY" else Decimal("-1")
            gross = (
                (fill - position.entry)
                / symbol_spec.trade_tick_size
                * symbol_spec.trade_tick_value_loss
                * position.volume
                * sign
            )
            net = gross - position.commission
            equity += net
            trades.append(
                BacktestTrade(
                    instrument=instrument,
                    direction=position.direction,
                    signal_time=position.signal_time,
                    entry_time=position.entry_time,
                    exit_time=last.timestamp + _TIMEFRAME_DURATION["5M"],
                    entry=position.entry,
                    exit=fill,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    volume=position.volume,
                    gross_pnl=gross,
                    commission=position.commission,
                    net_pnl=net,
                    result="WIN" if net > 0 else "LOSS",
                    r_multiple=net / position.risk_cash if position.risk_cash > 0 else _ZERO,
                )
            )
        else:
            warnings.append("Open position could not be force-closed: final spread is missing")

    wins = sum(trade.net_pnl > 0 for trade in trades)
    losses = sum(trade.net_pnl <= 0 for trade in trades)
    gross_profit = sum((max(_ZERO, trade.net_pnl) for trade in trades), _ZERO)
    gross_loss = sum((min(_ZERO, trade.net_pnl) for trade in trades), _ZERO)
    winning_trades = [trade for trade in trades if trade.net_pnl > 0]
    losing_trades = [trade for trade in trades if trade.net_pnl <= 0]
    average_win = (
        sum((trade.net_pnl for trade in winning_trades), _ZERO)
        / Decimal(len(winning_trades))
        if winning_trades
        else _ZERO
    )
    average_loss = (
        sum((trade.net_pnl for trade in losing_trades), _ZERO)
        / Decimal(len(losing_trades))
        if losing_trades
        else _ZERO
    )
    monthly: dict[str, list[BacktestTrade]] = {}
    for trade in trades:
        key = trade.exit_time.strftime("%Y-%m")
        monthly.setdefault(key, []).append(trade)
    monthly_breakdown = tuple(
        BacktestMonth(
            year_month=month,
            trade_count=len(rows),
            wins=sum(row.net_pnl > 0 for row in rows),
            losses=sum(row.net_pnl <= 0 for row in rows),
            net_pnl=sum((row.net_pnl for row in rows), _ZERO),
            win_rate_percent=(
                Decimal(sum(row.net_pnl > 0 for row in rows))
                / Decimal(len(rows))
                * _ONE_HUNDRED
            ),
        )
        for month, rows in sorted(monthly.items())
    )
    profit_factor = (
        gross_profit / abs(gross_loss) if gross_loss < 0 else None
    )
    expectancy = (
        sum((trade.r_multiple for trade in trades), _ZERO) / Decimal(len(trades))
        if trades
        else _ZERO
    )
    return BacktestResult(
        instrument=instrument,
        starting_equity=config.starting_equity,
        ending_equity=equity,
        net_return_percent=(equity - config.starting_equity)
        / config.starting_equity
        * _ONE_HUNDRED,
        trade_count=len(trades),
        wins=wins,
        losses=losses,
        win_rate_percent=Decimal(wins) / Decimal(len(trades)) * _ONE_HUNDRED
        if trades
        else _ZERO,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        average_win=average_win,
        average_loss=average_loss,
        largest_win=max((trade.net_pnl for trade in trades), default=_ZERO),
        largest_loss=min((trade.net_pnl for trade in trades), default=_ZERO),
        average_rr=expectancy,
        monthly_breakdown=monthly_breakdown,
        profit_factor=profit_factor,
        expectancy_r=expectancy,
        max_drawdown_percent=max_drawdown * _ONE_HUNDRED,
        max_daily_drawdown_percent=max_daily_drawdown * _ONE_HUNDRED,
        max_consecutive_losses=max_consecutive_losses,
        skipped_signals=skipped,
        trades=tuple(trades),
        warnings=tuple(dict.fromkeys(warnings)),
    )
