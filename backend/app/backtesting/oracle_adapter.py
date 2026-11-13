"""Adapter connecting chronological replay to the production Oracle analyzer.

Historical data callbacks must return point-in-time snapshots. In particular,
calendar callbacks must return only events that were known/scheduled as of the
requested timestamp, while retaining future scheduled release times so the
risk gate can avoid news windows. This module never calls live providers.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from decimal import Decimal

from app.analysis.oracle import analyze_pair
from app.backtesting.engine import Analyzer
from app.models.fundamental import EconomicEvent, PairBias
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle, Quote


PairBiasAt = Callable[[datetime], PairBias]
EconomicEventsAt = Callable[[datetime], tuple[EconomicEvent, ...]]
LiquidityLevelsAt = Callable[[datetime], tuple[LiquidityLevel, ...]]


def build_oracle_analyzer(
    *,
    instrument: str,
    pair_bias_at: PairBiasAt,
    economic_events_at: EconomicEventsAt,
    liquidity_levels_at: LiquidityLevelsAt | None = None,
) -> Analyzer:
    """Build a backtest callback that reuses the exact production decision chain.

    Each callback is queried with the simulation timestamp. Historical news and
    fundamental scoring belongs inside pair_bias_at, using its as-of argument.
    Calendar callbacks must provide the historical calendar snapshot, including
    future scheduled releases known at that time, not today's downloaded feed.
    """
    def analyze_at(
        as_of: datetime,
        history: Mapping[str, list[Candle]],
    ):
        if as_of.tzinfo is None:
            raise ValueError("backtest timestamp must be timezone-aware")
        pair_bias = pair_bias_at(as_of)
        if pair_bias.instrument != instrument:
            raise ValueError("historical pair bias instrument does not match")
        five_minute = history.get("5M", [])
        if not five_minute:
            raise ValueError("historical 5M candles are required")
        latest = five_minute[-1]
        quote = None
        if latest.bid is not None and latest.ask is not None and latest.ask >= latest.bid:
            quote = Quote(
                instrument=instrument,
                timestamp=as_of,
                bid=latest.bid,
                ask=latest.ask,
                mid=(latest.bid + latest.ask) / Decimal("2"),
                source="historical_5m_candle",
            )
        events = economic_events_at(as_of)
        levels = liquidity_levels_at(as_of) if liquidity_levels_at else ()
        return analyze_pair(
            candles_4h=history.get("4H", []),
            candles_1h=history.get("1H", []),
            candles_15m=history.get("15M", []),
            candles_5m=five_minute,
            pair_bias=pair_bias,
            liquidity_levels=levels,
            quote=quote,
            economic_events=events,
            checked_at=as_of,
        )

    return analyze_at
