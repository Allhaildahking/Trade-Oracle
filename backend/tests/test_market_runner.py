from datetime import UTC, datetime

# Ruff currently reports I001 for this valid first-party import block.
# Keep the test imports explicit while the upstream import-sort behavior is resolved.
# ruff: noqa: I001

import pytest

from app.analysis.market_runner import MarketRunner
from app.analysis.rotation import RotationDecision
from app.models.oracle import OracleAnalysis


ACTIVE = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "USDCAD")
CHECKED_AT = datetime(2026, 9, 25, 8, tzinfo=UTC)


def make_analysis(instrument: str, score: float) -> OracleAnalysis:
    return OracleAnalysis(
        instrument=instrument,
        decision="NO_TRADE",
        technical_score=score,
        weighted_score=score,
        setup=None,
        confirmation=None,
        trade=None,
        risk=None,
        reasons=("test",),
    )


class FakeOracle:
    def __init__(self) -> None:
        self.instruments: list[str] = []

    def analyze_pair(self, instrument: str, *, checked_at: datetime) -> OracleAnalysis:
        self.instruments.append(instrument)
        return make_analysis(instrument, 0.5)


def test_market_runner_executes_active_six_pair_universe() -> None:
    oracle = FakeOracle()
    runner = MarketRunner(oracle=oracle)

    result, analyses = runner.scan(checked_at=CHECKED_AT)

    assert result.active_instruments == ACTIVE
    assert oracle.instruments == list(ACTIVE)
    assert tuple(item.instrument for item in analyses) == ACTIVE
    assert len(result.ranked) == 6


def test_market_runner_uses_rotated_sixth_pair() -> None:
    oracle = FakeOracle()
    runner = MarketRunner(oracle=oracle)
    rotation = RotationDecision(
        active_instrument="AUDUSD",
        evaluations=(),
        changed=True,
        reason="test rotation",
    )

    result, analyses = runner.scan(checked_at=CHECKED_AT, rotation=rotation)

    expected = ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "XAUUSD", "AUDUSD")
    assert result.active_instruments == expected
    assert oracle.instruments == list(expected)
    assert tuple(item.instrument for item in analyses) == expected


def test_market_runner_rejects_naive_timestamp() -> None:
    runner = MarketRunner(oracle=FakeOracle())

    with pytest.raises(ValueError, match="timezone-aware"):
        runner.scan(checked_at=datetime(2026, 9, 25, 8))

def test_market_runner_renders_report_from_same_scan() -> None:
    oracle = FakeOracle()
    runner = MarketRunner(oracle=oracle)

    report, analyses = runner.run_report(checked_at=CHECKED_AT)

    assert "TRADE ORACLE MARKET REPORT" in report
    assert "Active universe: EURUSD, GBPUSD, USDJPY, USDCHF, XAUUSD, USDCAD" in report
    assert "1. XAUUSD | NO_TRADE | score=0.500 | direction=N/A | RR=N/A" in report
    assert "6. EURUSD | NO_TRADE | score=0.500 | direction=N/A | RR=N/A" in report
    assert tuple(item.instrument for item in analyses) == ACTIVE
