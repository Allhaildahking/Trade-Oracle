from decimal import Decimal

from app.analysis.report import render_market_report
from app.models.market_scan import MarketScan, PairAssessment


def make_scan() -> MarketScan:
    assessments = (
        PairAssessment(
            instrument="EURUSD",
            decision="TRADE",
            weighted_score=0.82,
            risk_reward=3.0,
            direction="BUY",
            entry=Decimal("1.1000"),
            stop_loss=Decimal("1.0950"),
            take_profit=Decimal("1.1150"),
            invalidation=Decimal("1.0940"),
            reasons=("trade setup",),
        ),
        PairAssessment(
            instrument="GBPUSD",
            decision="WAIT",
            weighted_score=0.61,
            risk_reward=None,
            direction=None,
            reasons=("waiting",),
        ),
        PairAssessment(
            instrument="USDJPY",
            decision="BLOCKED",
            weighted_score=0.55,
            risk_reward=None,
            direction=None,
            reasons=("news",),
        ),
    )
    return MarketScan(
        assessments=assessments,
        ranked=assessments,
        active_instruments=("EURUSD", "GBPUSD", "USDJPY"),
    )


def test_market_report_contains_ranked_pair_details() -> None:
    report = render_market_report(make_scan())

    assert "TRADE ORACLE MARKET REPORT" in report
    assert "1. EURUSD | TRADE | score=0.820 | direction=BUY | RR=3.00" in report
    assert "  Entry: 1.1000" in report
    assert "  SL: 1.0950" in report
    assert "  TP: 1.1150" in report
    assert "  Invalidation: 1.0940" in report
    assert "2. GBPUSD | WAIT | score=0.610 | direction=N/A | RR=N/A" in report
    assert "3. USDJPY | BLOCKED | score=0.550 | direction=N/A | RR=N/A" in report
    assert "TOP RESULT: EURUSD (TRADE)" in report


def test_market_report_preserves_active_universe() -> None:
    report = render_market_report(make_scan())

    assert "Active universe: EURUSD, GBPUSD, USDJPY" in report
