from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.analysis.market_runner import MarketRunner
from app.analysis.scanner import scan_analyses
from app.models.oracle import OracleAnalysis
from app.models.trade import TradeCandidate

ACTIVE = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "USDCAD")
CHECKED_AT = datetime(2026, 9, 25, 8, tzinfo=UTC)


def make_analysis(instrument: str, decision: str, score: float) -> OracleAnalysis:
    trade = TradeCandidate(
        instrument=instrument,
        direction="BUY",
        status="VALID" if decision == "TRADE" else "REJECTED",
        entry=Decimal("1.1000"),
        stop_loss=Decimal("1.0980"),
        take_profit=Decimal("1.1050"),
        risk_distance=Decimal("0.0020"),
        reward_distance=Decimal("0.0050"),
        risk_reward=Decimal("2.5"),
        invalidation=Decimal("1.0980"),
        reasons=(),
    )
    return OracleAnalysis(
        instrument=instrument,
        decision=decision,
        technical_score=score,
        weighted_score=score,
        setup=None,
        confirmation=None,
        trade=trade,
        risk=None,
        reasons=(f"decision={decision}",),
    )


def test_scan_analyses_ranks_completed_results() -> None:
    analyses = tuple(
        make_analysis(
            pair,
            "TRADE" if pair == "EURUSD" else "NO_TRADE",
            0.9 if pair == "EURUSD" else 0.7,
        )
        for pair in ACTIVE
    )
    result = scan_analyses(analyses, active_instruments=ACTIVE)

    assert result.active_instruments == ACTIVE
    assert result.ranked[0].instrument == "EURUSD"
    assert result.ranked[0].decision == "TRADE"


def test_scan_analyses_requires_complete_universe() -> None:
    with pytest.raises(ValueError, match="missing scanner analyses"):
        scan_analyses(
            tuple(make_analysis(pair, "NO_TRADE", 0.5) for pair in ACTIVE[:5]),
            active_instruments=ACTIVE,
        )


class FakeOracle:
    def __init__(self) -> None:
        self.instruments: list[str] = []

    def analyze_pair(self, instrument: str, *, checked_at: datetime) -> OracleAnalysis:
        self.instruments.append(instrument)
        return make_analysis(instrument, "NO_TRADE", 0.5)


def test_market_runner_executes_active_six_pair_universe() -> None:
    oracle = FakeOracle()
    runner = MarketRunner(oracle=oracle)

    result, analyses = runner.scan(checked_at=CHECKED_AT)

    assert result.active_instruments == ACTIVE
    assert oracle.instruments == list(ACTIVE)
    assert tuple(item.instrument for item in analyses) == ACTIVE
    assert len(result.ranked) == 6


def test_market_runner_rejects_naive_timestamp() -> None:
    runner = MarketRunner(oracle=FakeOracle())

    with pytest.raises(ValueError, match="timezone-aware"):
        runner.scan(checked_at=datetime(2026, 9, 25, 8))
