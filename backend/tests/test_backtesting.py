from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.backtesting.engine import BacktestConfig, run_backtest
from app.models.market import Candle
from app.models.oracle import OracleAnalysis
from app.models.risk import RiskValidation
from app.models.symbol import SymbolSpec
from app.models.trade import TradeCandidate


START = datetime(2026, 1, 5, 8, tzinfo=timezone.utc)


def _candle(
    timeframe: str,
    timestamp: datetime,
    *,
    open_price: str = "1.1000",
    high: str = "1.1010",
    low: str = "1.0990",
    close: str = "1.1000",
) -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe=timeframe,
        timestamp=timestamp,
        open=Decimal(open_price),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        bid=Decimal("1.0999"),
        ask=Decimal("1.1001"),
        is_complete=True,
    )


def _analysis() -> OracleAnalysis:
    trade = TradeCandidate(
        instrument="EURUSD",
        direction="BUY",
        status="VALID",
        entry=Decimal("1.1000"),
        stop_loss=Decimal("1.0980"),
        take_profit=Decimal("1.1050"),
        risk_distance=Decimal("0.0020"),
        reward_distance=Decimal("0.0050"),
        risk_reward=Decimal("2.5"),
        invalidation=Decimal("1.0980"),
        reasons=(),
    )
    risk = RiskValidation(
        instrument="EURUSD",
        decision="TRADE",
        valid=True,
        reasons=(),
        checked_at=START,
        expires_at=START + timedelta(minutes=30),
    )
    return OracleAnalysis(
        instrument="EURUSD",
        decision="TRADE",
        technical_score=1.0,
        weighted_score=1.0,
        setup=None,
        confirmation=None,
        trade=trade,
        risk=risk,
        reasons=(),
    )


def _inputs(exit_bar: Candle) -> dict[str, list[Candle]]:
    return {
        "4H": [_candle("4H", START - timedelta(hours=4))],
        "1H": [_candle("1H", START - timedelta(hours=1))],
        "15M": [_candle("15M", START - timedelta(minutes=15))],
        "5M": [
            _candle("5M", START),
            exit_bar,
            *[
                _candle("5M", START + timedelta(minutes=5 * index))
                for index in range(2, 6)
            ],
        ],
    }


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


def test_backtest_uses_only_closed_candles_and_enters_next_bar() -> None:
    exit_bar = _candle(
        "5M",
        START + timedelta(minutes=5),
        open_price="1.1000",
        high="1.1060",
        low="1.0990",
        close="1.1040",
    )
    seen: list[tuple[datetime, int]] = []

    def analyzer(as_of, history):
        seen.append((as_of, len(history["5M"])))
        assert all(row.timestamp + timedelta(minutes=5) <= as_of for row in history["5M"])
        return _analysis() if len(seen) == 1 else OracleAnalysis(
            instrument="EURUSD",
            decision="NO_TRADE",
            technical_score=0,
            weighted_score=0,
            setup=None,
            confirmation=None,
            trade=None,
            risk=None,
            reasons=(),
        )

    result = run_backtest(
        instrument="EURUSD",
        candles=_inputs(exit_bar),
        symbol_spec=_spec(),
        analyzer=analyzer,
        config=BacktestConfig(starting_equity=Decimal("100")),
    )

    assert result.trade_count == 1
    assert result.trades[0].entry_time == exit_bar.timestamp
    assert result.trades[0].result == "WIN"
    assert seen[0][0] == START + timedelta(minutes=5)
    assert seen[0][1] == 1


def test_stop_loss_wins_when_stop_and_target_touch_same_bar() -> None:
    exit_bar = _candle(
        "5M",
        START + timedelta(minutes=5),
        high="1.1060",
        low="1.0970",
    )
    calls = 0

    def analyzer(as_of, history):
        nonlocal calls
        calls += 1
        return _analysis() if calls == 1 else OracleAnalysis(
            instrument="EURUSD",
            decision="NO_TRADE",
            technical_score=0,
            weighted_score=0,
            setup=None,
            confirmation=None,
            trade=None,
            risk=None,
            reasons=(),
        )

    result = run_backtest(
        instrument="EURUSD",
        candles=_inputs(exit_bar),
        symbol_spec=_spec(),
        analyzer=analyzer,
        config=BacktestConfig(starting_equity=Decimal("100")),
    )

    assert result.trade_count == 1
    assert result.trades[0].result == "LOSS"
    assert result.trades[0].exit <= Decimal("1.0980")


def test_missing_spread_blocks_entry_instead_of_assuming_zero() -> None:
    candles = _inputs(_candle("5M", START + timedelta(minutes=5)))
    candles["5M"][1] = Candle(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=START + timedelta(minutes=5),
        open=Decimal("1.1000"),
        high=Decimal("1.1010"),
        low=Decimal("1.0990"),
        close=Decimal("1.1000"),
    )
    calls = 0

    def analyzer(as_of, history):
        nonlocal calls
        calls += 1
        return _analysis() if calls == 1 else OracleAnalysis(
            instrument="EURUSD",
            decision="NO_TRADE",
            technical_score=0,
            weighted_score=0,
            setup=None,
            confirmation=None,
            trade=None,
            risk=None,
            reasons=(),
        )

    result = run_backtest(
        instrument="EURUSD",
        candles=candles,
        symbol_spec=_spec(),
        analyzer=analyzer,
        config=BacktestConfig(starting_equity=Decimal("100")),
    )

    assert result.trade_count == 0
    assert result.skipped_signals >= 1
    assert any("spread" in warning for warning in result.warnings)
