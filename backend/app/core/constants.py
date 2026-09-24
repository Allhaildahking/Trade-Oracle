"""V1 constants and controlled vocabulary for Trade Oracle."""

from __future__ import annotations

CORE_INSTRUMENTS: tuple[str, ...] = (
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "XAUUSD",
)

CANDIDATE_INSTRUMENTS: tuple[str, ...] = (
    "USDCAD",
    "AUDUSD",
    "NZDUSD",
)

TIMEFRAMES: tuple[str, ...] = ("4H", "1H", "15M", "5M")

TECHNICAL_CONCEPTS: tuple[str, ...] = (
    "BOS",
    "CHoCH",
    "LIQUIDITY_SWEEP",
    "PREVIOUS_DAY_WEEK_HIGH_LOW",
    "SESSION_HIGH_LOW",
    "DISPLACEMENT",
    "BREAK_RETEST",
)

MINIMUM_RR = 2.5
FUNDAMENTAL_WEIGHT = 0.51
TECHNICAL_WEIGHT = 0.49

SIGNAL_STATES: tuple[str, ...] = (
    "WATCH",
    "ACTIVE",
    "BREAKEVEN",
    "TP_HIT",
    "INVALIDATED",
    "EXPIRED",
)

DECISIONS: tuple[str, ...] = (
    "TRADE",
    "WATCH",
    "WAIT",
    "NO_TRADE",
    "BLOCKED",
)

NEWS_TRADE_ADVICE: tuple[str, ...] = (
    "HOLD",
    "PROTECT",
    "REDUCE",
    "EXIT",
    "NO_CHANGE",
)

MARKET_REGIMES: tuple[str, ...] = (
    "TRENDING",
    "RANGING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "UNSTABLE_NEWS",
)
