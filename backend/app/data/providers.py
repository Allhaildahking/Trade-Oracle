"""Live provider assembly for Trade Oracle."""

from __future__ import annotations

from app.analysis.runner import OracleRunner
from app.data.alpha_vantage import AlphaVantageNewsProvider
from app.data.finance_calendar import FinanceCalendarProvider
from app.data.twelve_data import TwelveDataProvider


def build_oracle_runner() -> OracleRunner:
    """Build an OracleRunner from the configured live provider adapters."""
    return OracleRunner(
        market=TwelveDataProvider(),
        calendar=FinanceCalendarProvider(),
        news=AlphaVantageNewsProvider(),
    )
