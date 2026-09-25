from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.analysis.decision import DecisionContext
from app.analysis.scanner import scan
from app.models.confirmation import Confirmation5M
from app.models.market_scan import MarketScan
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate

ACTIVE = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "USDCAD")
CHECKED_AT = datetime(2026, 9, 25, 1, 0, tzinfo=UTC)


def make_context(instrument: str, score: float, *, ready: bool = True, risk_decision: str = "TRADE") -> DecisionContext:
    setup_status = "CANDIDATE" if ready else "REJECTED"
    confirmation_status = "CONFIRMED" if ready else "REJECTED"
    trade_status = "VALID" if ready else "REJECTED"
    setup = SetupCandidate(
        instrument=instrument,
        timeframe="15M",
        direction="BUY",
        status=setup_status,
        fundamental_score=Decimal(str(score)),
        regime=None,
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=(),
    )
    confirmation = Confirmation5M(
        instrument=instrument,
        timeframe="5M",
        direction="BUY",
        status=confirmation_status,
        structure_events=(),
        displacement=None,
        sweep=None,
        reasons=(),
    )
    trade = TradeCandidate(
        instrument=instrument,
        direction="BUY",
        status=trade_status,
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
        instrument=instrument,
        decision=risk_decision,
        valid=risk_decision == "TRADE",
        reasons=(),
        checked_at=CHECKED_AT,
    )
    return DecisionContext(
        fundamental_score=score,
        technical_score=score,
        setup=setup,
        confirmation=confirmation,
        trade=trade,
        risk=risk,
    )


def test_scanner_requires_six_unique_supported_pairs() -> None:
    with pytest.raises(ValueError, match="exactly 6"):
        scan((), active_instruments=ACTIVE[:5])
    with pytest.raises(ValueError, match="unique"):
        scan((), active_instruments=ACTIVE[:5] + ("EURUSD",))
    with pytest.raises(ValueError, match="unsupported"):
        scan((), active_instruments=ACTIVE[:5] + ("GBPJPY",))


def test_scanner_evaluates_all_six_pairs() -> None:
    result = scan(tuple(make_context(pair, 0.8) for pair in ACTIVE), active_instruments=ACTIVE)
    assert isinstance(result, MarketScan)
    assert result.active_instruments == ACTIVE
    assert tuple(item.instrument for item in result.assessments) == ACTIVE
    assert all(item.decision == "TRADE" for item in result.assessments)


def test_scanner_ranks_by_decision_before_score() -> None:
    contexts = (
        make_context("EURUSD", 0.95),
        make_context("GBPUSD", 0.70),
        make_context("USDJPY", 0.99, ready=False),
        make_context("USDCHF", 0.65),
        make_context("XAUUSD", 0.60, risk_decision="WAIT"),
        make_context("USDCAD", 0.90, risk_decision="BLOCKED"),
    )
    result = scan(contexts, active_instruments=ACTIVE)
    assert tuple(item.instrument for item in result.ranked) == (
        "EURUSD",
        "GBPUSD",
        "USDCHF",
        "XAUUSD",
        "USDJPY",
        "USDCAD",
    )


def test_scanner_never_promotes_no_trade_or_blocked() -> None:
    contexts = tuple(
        make_context(pair, 0.99, ready=False, risk_decision="BLOCKED")
        for pair in ACTIVE
    )
    result = scan(contexts, active_instruments=ACTIVE)
    assert all(item.decision == "NO_TRADE" for item in result.assessments)
    assert all(item.decision == "NO_TRADE" for item in result.ranked)


def test_scanner_rejects_missing_or_duplicate_contexts() -> None:
    with pytest.raises(ValueError, match="missing scanner contexts"):
        scan((make_context("EURUSD", 0.8),), active_instruments=ACTIVE)
    with pytest.raises(ValueError, match="duplicate scanner context"):
        scan(
            tuple(make_context(pair, 0.8) for pair in ACTIVE) + (make_context("EURUSD", 0.7),),
            active_instruments=ACTIVE,
        )
