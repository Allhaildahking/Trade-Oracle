from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.report import render_market_scan
from app.models.market_scan import MarketScan, PairAssessment


def test_render_market_scan_is_concise_and_ranked() -> None:
    scan = MarketScan(
        assessments=(),
        ranked=(
            PairAssessment(
                instrument="EURUSD",
                decision="TRADE",
                weighted_score=0.812,
                risk_reward=2.5,
                direction="BUY",
                reasons=("aligned",),
            ),
            PairAssessment(
                instrument="USDJPY",
                decision="NO_TRADE",
                weighted_score=0.341,
                risk_reward=None,
                direction=None,
                reasons=("rejected",),
            ),
        ),
        active_instruments=("EURUSD", "USDJPY", "GBPUSD", "USDCHF", "XAUUSD", "USDCAD"),
    )

    output = render_market_scan(scan)

    assert output == (
        "TRADE ORACLE | MARKET SCAN\n\n"
        "1. EURUSD | TRADE BUY | score 0.812 RR 2.50\n"
        "2. USDJPY | NO_TRADE | score 0.341"
    )
