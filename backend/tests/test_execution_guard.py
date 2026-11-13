from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.execution.execution_guard import ExecutionPolicy, approve_execution
from app.models.account import AccountSnapshot
from app.models.market import Quote
from app.models.oracle import OracleAnalysis
from app.models.risk import RiskValidation
from app.models.symbol import SymbolSpec
from app.models.trade import TradeCandidate

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)


@pytest.fixture
def policy():
    return ExecutionPolicy(
        enabled=True,
        risk_percent=Decimal("10"),
        max_risk_percent=Decimal("10"),
        allowed_instruments=("XAUUSDmicro",),
    )


@pytest.fixture
def account():
    return AccountSnapshot(
        equity=Decimal("1000"),
        currency="USD",
        is_demo=True,
        leverage=100,
    )


@pytest.fixture
def quote():
    return Quote(
        instrument="XAUUSDmicro",
        timestamp=NOW - timedelta(seconds=1),
        bid=Decimal("2350.10"),
        ask=Decimal("2350.20"),
        mid=Decimal("2350.15"),
        source="test",
    )


@pytest.fixture
def spec():
    return SymbolSpec(
        instrument="XAUUSDmicro",
        trade_tick_size=Decimal("0.01"),
        trade_tick_value_loss=Decimal("0.01"),
        volume_min=Decimal("0.1"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.1"),
        contract_size=Decimal("1"),
    )


@pytest.fixture
def analysis():
    trade = TradeCandidate(
        instrument="XAUUSDmicro",
        direction="BUY",
        status="VALID",
        entry=Decimal("2350.20"),
        stop_loss=Decimal("2349.20"),
        take_profit=Decimal("2352.70"),
        risk_distance=Decimal("1"),
        reward_distance=Decimal("2.5"),
        risk_reward=Decimal("2.5"),
        invalidation=None,
        reasons=(),
    )
    risk = RiskValidation(
        instrument="XAUUSDmicro",
        decision="TRADE",
        valid=True,
        reasons=(),
        checked_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(minutes=5),
    )
    return OracleAnalysis(
        instrument="XAUUSDmicro",
        decision="TRADE",
        technical_score=0.8,
        weighted_score=0.8,
        setup=None,
        confirmation=None,
        trade=trade,
        risk=risk,
        reasons=(),
    )


def run_gate(analysis, account, quote, spec, policy, **overrides):
    args = {
        "analysis": analysis,
        "account": account,
        "quote": quote,
        "symbol_spec": spec,
        "now": NOW,
        "open_positions": 0,
        "daily_realized_loss": Decimal("0"),
        "policy": policy,
    }
    args.update(overrides)
    return approve_execution(**args)


def test_approves_valid_demo_trade(analysis, account, quote, spec, policy):
    result = run_gate(analysis, account, quote, spec, policy)
    assert result.approved
    assert result.volume is not None
    assert result.estimated_loss <= result.risk_budget


def test_execution_disabled_by_default(analysis, account, quote, spec):
    result = run_gate(
        analysis, account, quote, spec, ExecutionPolicy(enabled=False)
    )
    assert not result.approved
    assert "disabled" in result.reasons[-1]


def test_rejects_live_account(analysis, account, quote, spec, policy):
    live = AccountSnapshot(Decimal("1000"), "USD", False, 100)
    result = run_gate(analysis, live, quote, spec, policy)
    assert not result.approved
    assert "demo account required" in result.reasons[-1]


def test_rejects_non_trade_oracle_decision(analysis, account, quote, spec, policy):
    blocked = OracleAnalysis(
        instrument=analysis.instrument,
        decision="NO_TRADE",
        technical_score=0,
        weighted_score=0,
        setup=None,
        confirmation=None,
        trade=analysis.trade,
        risk=analysis.risk,
        reasons=(),
    )
    result = run_gate(blocked, account, quote, spec, policy)
    assert not result.approved
    assert "not TRADE" in result.reasons[-1]


def test_rejects_stale_quote(analysis, account, quote, spec, policy):
    stale = Quote(
        instrument=quote.instrument,
        timestamp=NOW - timedelta(minutes=1),
        bid=quote.bid,
        ask=quote.ask,
        mid=quote.mid,
    )
    result = run_gate(analysis, account, stale, spec, policy)
    assert not result.approved
    assert "stale" in result.reasons[-1]


def test_rejects_expired_risk_validation(analysis, account, quote, spec, policy):
    expired_risk = RiskValidation(
        instrument="XAUUSDmicro",
        decision="TRADE",
        valid=True,
        reasons=(),
        checked_at=NOW - timedelta(minutes=10),
        expires_at=NOW - timedelta(seconds=1),
    )
    expired = OracleAnalysis(
        instrument=analysis.instrument,
        decision="TRADE",
        technical_score=0.8,
        weighted_score=0.8,
        setup=None,
        confirmation=None,
        trade=analysis.trade,
        risk=expired_risk,
        reasons=(),
    )
    result = run_gate(expired, account, quote, spec, policy)
    assert not result.approved
    assert "expired" in result.reasons[-1]


def test_rejects_when_open_position_limit_reached(
    analysis, account, quote, spec, policy
):
    result = run_gate(
        analysis, account, quote, spec, policy, open_positions=1
    )
    assert not result.approved
    assert "maximum open-position" in result.reasons[-1]


def test_rejects_daily_loss_limit(analysis, account, quote, spec, policy):
    result = run_gate(
        analysis,
        account,
        quote,
        spec,
        policy,
        daily_realized_loss=Decimal("200"),
    )
    assert not result.approved
    assert "daily realized-loss" in result.reasons[-1]


def test_rejects_symbol_not_allowlisted(analysis, account, quote, spec):
    restricted = ExecutionPolicy(
        enabled=True,
        allowed_instruments=("EURUSD",),
    )
    result = run_gate(analysis, account, quote, spec, restricted)
    assert not result.approved
    assert "not allowlisted" in result.reasons[-1]


def test_rejects_bad_clock_and_negative_loss(analysis, account, quote, spec, policy):
    with pytest.raises(ValueError, match="timezone-aware"):
        run_gate(
            analysis,
            account,
            quote,
            spec,
            policy,
            now=datetime(2026, 11, 13),
        )
    with pytest.raises(ValueError, match="must not be negative"):
        run_gate(
            analysis,
            account,
            quote,
            spec,
            policy,
            daily_realized_loss=Decimal("-1"),
        )


def test_risk_and_daily_limits_halve_at_thirty_dollars(
    analysis, quote, spec, policy
):
    small = AccountSnapshot(Decimal("20"), "USD", True, 100)
    threshold = AccountSnapshot(Decimal("30"), "USD", True, 100)

    small_result = run_gate(analysis, small, quote, spec, policy)
    threshold_result = run_gate(analysis, threshold, quote, spec, policy)

    assert small_result.approved
    assert threshold_result.approved
    assert small_result.risk_budget == Decimal("2")
    assert threshold_result.risk_budget == Decimal("1.5")

    small_daily_stop = run_gate(
        analysis,
        small,
        quote,
        spec,
        policy,
        daily_realized_loss=Decimal("4"),
    )
    threshold_daily_stop = run_gate(
        analysis,
        threshold,
        quote,
        spec,
        policy,
        daily_realized_loss=Decimal("3"),
    )
    assert not small_daily_stop.approved
    assert not threshold_daily_stop.approved
    assert "daily realized-loss" in small_daily_stop.reasons[-1]
    assert "daily realized-loss" in threshold_daily_stop.reasons[-1]


def test_policy_defaults_to_ten_percent_and_twenty_percent():
    policy = ExecutionPolicy()
    assert policy.risk_percent == Decimal("10.0")
    assert policy.max_daily_loss_percent == Decimal("20.0")
    assert policy.reduced_risk_balance_threshold == Decimal("30.0")
    assert policy.reduced_risk_multiplier == Decimal("0.5")


@pytest.mark.parametrize(
    ("equity", "expected_risk"),
    [
        (Decimal("5"), Decimal("10")),
        (Decimal("10"), Decimal("10")),
        (Decimal("29.99"), Decimal("10")),
        (Decimal("30"), Decimal("5")),
        (Decimal("100"), Decimal("5")),
    ],
)
def test_balance_based_risk_tiers(
    analysis, quote, spec, policy, equity, expected_risk
):
    small_account = AccountSnapshot(equity, "USD", True, 100)
    result = run_gate(analysis, small_account, quote, spec, policy)
    assert result.approved
    assert result.risk_budget == equity * expected_risk / Decimal("100")
