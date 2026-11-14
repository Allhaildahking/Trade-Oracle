"""Technical-only analyzer for diagnostic historical backtests.

This adapter deliberately excludes fundamentals and economic-calendar filtering.
It derives directional bias from completed higher-timeframe market structure and
reuses the production 15M setup, 5M confirmation, and trade-construction logic.
Its output is diagnostic only and must not be used for live execution.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.analysis.confirmation_5m import confirm_5m
from app.analysis.liquidity import map_liquidity
from app.analysis.setup import detect_setup_candidate
from app.analysis.structure import detect_structure
from app.analysis.trade import construct_trade
from app.backtesting.engine import Analyzer
from app.models.fundamental import CurrencyBias, PairBias
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle, Quote
from app.models.oracle import OracleAnalysis
from app.models.risk import RiskValidation

LiquidityLevelsAt = Callable[
    [datetime, Mapping[str, list[Candle]]], tuple[LiquidityLevel, ...]
]

_DEFAULT_EXPIRY = timedelta(minutes=30)
_DEFAULT_MAX_SPREAD_RATIO = Decimal("0.10")
_MINIMUM_15M_CANDLES = 71


def build_technical_only_analyzer(
    *,
    instrument: str,
    liquidity_levels_at: LiquidityLevelsAt | None = None,
    expiry: timedelta = _DEFAULT_EXPIRY,
    max_spread_ratio: Decimal = _DEFAULT_MAX_SPREAD_RATIO,
) -> Analyzer:
    """Build an isolated analyzer that excludes all fundamental/news filters.

    The directional bias is the most recent completed 4H/1H structure event.
    The normal production setup, confirmation, and trade-construction
    functions remain in use. Calendar/news checks are explicitly excluded and
    recorded in every actionable diagnostic result.
    """
    if not instrument.strip():
        raise ValueError("instrument must not be blank")
    if expiry <= timedelta(0):
        raise ValueError("expiry must be positive")
    if max_spread_ratio < 0:
        raise ValueError("max_spread_ratio must not be negative")

    def analyze_at(
        as_of: datetime,
        history: Mapping[str, list[Candle]],
    ) -> OracleAnalysis:
        if as_of.tzinfo is None:
            raise ValueError("backtest timestamp must be timezone-aware")

        candles_4h = history.get("4H", [])
        candles_1h = history.get("1H", [])
        candles_15m = history.get("15M", [])
        candles_5m = history.get("5M", [])
        _validate_history(instrument, candles_4h, "4H")
        _validate_history(instrument, candles_1h, "1H")
        _validate_history(instrument, candles_15m, "15M")
        _validate_history(instrument, candles_5m, "5M")
        if len(candles_15m) < _MINIMUM_15M_CANDLES:
            return _no_trade(
                instrument,
                "15M regime warm-up requires at least "
                f"{_MINIMUM_15M_CANDLES} completed candles",
            )

        htf_structure = (
            detect_structure(candles_4h),
            detect_structure(candles_1h),
        )
        pair_bias = _structure_bias(instrument, htf_structure)
        if pair_bias is None:
            return _no_trade(
                instrument,
                "no completed 4H/1H structure event is available for directional bias",
            )

        levels = (
            liquidity_levels_at(as_of, history)
            if liquidity_levels_at is not None
            else map_liquidity(candles_15m)
        )
        setup = detect_setup_candidate(
            candles_15m,
            pair_bias=pair_bias,
            htf_structure=htf_structure,
            liquidity_levels=levels,
        )
        setup = replace(
            setup,
            reasons=tuple(
                reason.replace("fundamental bias:", "technical HTF bias:")
                for reason in setup.reasons
            ),
        )
        technical_score = _setup_score(setup)
        if setup.status != "CANDIDATE":
            return OracleAnalysis(
                instrument=instrument,
                decision="NO_TRADE",
                technical_score=technical_score,
                weighted_score=technical_score,
                setup=setup,
                confirmation=None,
                trade=None,
                risk=None,
                reasons=(
                    "technical-only mode: fundamental and calendar filters are excluded",
                    *setup.reasons,
                ),
            )

        confirmation = confirm_5m(
            candles_5m,
            setup=setup,
            liquidity_levels=levels,
        )
        technical_score = _confirmation_score(setup, confirmation)
        if confirmation.status != "CONFIRMED":
            return OracleAnalysis(
                instrument=instrument,
                decision="WATCH",
                technical_score=technical_score,
                weighted_score=technical_score,
                setup=setup,
                confirmation=confirmation,
                trade=None,
                risk=None,
                reasons=(
                    "technical-only mode: fundamental and calendar filters are excluded",
                    *setup.reasons,
                    *confirmation.reasons,
                ),
            )

        trade = construct_trade(setup=setup, confirmation=confirmation)
        if trade.status != "VALID":
            return OracleAnalysis(
                instrument=instrument,
                decision="NO_TRADE",
                technical_score=technical_score,
                weighted_score=technical_score,
                setup=setup,
                confirmation=confirmation,
                trade=trade,
                risk=None,
                reasons=(*setup.reasons, *confirmation.reasons, *trade.reasons),
            )

        latest = candles_5m[-1]
        quote = None
        if (
            latest.bid is not None
            and latest.ask is not None
            and latest.bid > 0
            and latest.ask >= latest.bid
        ):
            quote = Quote(
                instrument=instrument,
                timestamp=as_of,
                bid=latest.bid,
                ask=latest.ask,
                mid=(latest.bid + latest.ask) / Decimal("2"),
                source="historical_5m_candle",
            )

        risk = _technical_risk(
            trade=trade,
            setup_regime=setup.regime.regime,
            quote=quote,
            checked_at=as_of,
            expiry=expiry,
            max_spread_ratio=max_spread_ratio,
        )
        decision = "TRADE" if risk.valid else (
            "WAIT" if risk.decision == "WAIT" else "BLOCKED"
        )
        return OracleAnalysis(
            instrument=instrument,
            decision=decision,
            technical_score=technical_score,
            weighted_score=technical_score,
            setup=setup,
            confirmation=confirmation,
            trade=trade,
            risk=risk,
            reasons=(
                "TECHNICAL-ONLY DIAGNOSTIC: fundamentals and economic-calendar "
                "filters are excluded; this is not a production trade signal",
                *setup.reasons,
                *confirmation.reasons,
                *trade.reasons,
                *risk.reasons,
            ),
        )

    return analyze_at


def _validate_history(
    instrument: str,
    candles: list[Candle],
    timeframe: str,
) -> None:
    if not candles:
        raise ValueError(f"{timeframe} candles must not be empty")
    if any(candle.instrument != instrument for candle in candles):
        raise ValueError(f"{timeframe} candle instrument must match requested instrument")
    if any(candle.timeframe != timeframe for candle in candles):
        raise ValueError(f"{timeframe} candles must use timeframe {timeframe}")
    if any(not candle.is_complete for candle in candles):
        raise ValueError(f"{timeframe} history contains an incomplete candle")
    if any(candle.timestamp.tzinfo is None for candle in candles):
        raise ValueError(f"{timeframe} candle timestamps must be timezone-aware")
    if any(
        candles[index].timestamp >= candles[index + 1].timestamp
        for index in range(len(candles) - 1)
    ):
        raise ValueError(f"{timeframe} candles must be strictly chronological")


def _structure_bias(
    instrument: str,
    snapshots: tuple,
) -> PairBias | None:
    events = [
        event
        for snapshot in snapshots
        for event in snapshot.events
    ]
    if not events:
        return None
    latest = max(events, key=lambda event: event.timestamp)
    direction = "BUY" if latest.direction == "BULLISH" else "SELL"
    base_currency, quote_currency = _instrument_currencies(instrument)
    zero = Decimal("0")
    base = CurrencyBias(base_currency, zero, ("direction derived from HTF structure",))
    quote = CurrencyBias(quote_currency, zero, ("technical-only diagnostic mode",))
    return PairBias(
        instrument=instrument,
        base=base,
        quote=quote,
        score=zero,
        direction=direction,
        evidence=(f"direction derived from {latest.timeframe} {latest.kind}",),
    )


def _instrument_currencies(instrument: str) -> tuple[str, str]:
    symbol = instrument.upper()
    if symbol.startswith("XAUUSD"):
        return "XAU", "USD"
    if len(symbol) == 6 and symbol.isalpha():
        return symbol[:3], symbol[3:]
    return symbol, "UNKNOWN"


def _setup_score(setup) -> float:
    score = 0.20 if setup.structure_events else 0.0
    score += 0.15 if setup.sweep is not None else 0.0
    score += 0.15 if setup.displacement is not None else 0.0
    score += 0.15 if setup.break_retest is not None else 0.0
    return round(score, 4)


def _confirmation_score(setup, confirmation) -> float:
    score = _setup_score(setup)
    score += 0.20 if confirmation.structure_events else 0.0
    score += 0.15 if confirmation.displacement is not None else 0.0
    return round(min(1.0, score), 4)


def _technical_risk(
    *,
    trade,
    setup_regime: str,
    quote: Quote | None,
    checked_at: datetime,
    expiry: timedelta,
    max_spread_ratio: Decimal,
) -> RiskValidation:
    reasons = [
        "fundamental direction and economic-calendar filters are intentionally excluded",
        "technical-only results are diagnostic and are not approved for live execution",
    ]
    blocked = False
    waiting = False

    if trade.risk_reward is None or trade.risk_reward < Decimal("2.5"):
        reasons.append("risk/reward is below the 2.5 minimum")
        blocked = True
    if setup_regime in {"UNSTABLE", "HIGH_VOLATILITY"}:
        reasons.append(f"regime {setup_regime} is incompatible with a normal trade")
        blocked = True
    if quote is None:
        reasons.append("historical quote/spread is unavailable")
        waiting = True
    elif trade.risk_distance is None or trade.risk_distance <= 0:
        reasons.append("trade risk distance is unavailable")
        blocked = True
    elif (quote.ask - quote.bid) / trade.risk_distance > max_spread_ratio:
        reasons.append("spread is too large relative to trade risk")
        blocked = True
    else:
        reasons.append("historical spread passes the configured risk-distance limit")

    decision = "BLOCKED" if blocked else "WAIT" if waiting else "TRADE"
    return RiskValidation(
        instrument=trade.instrument,
        decision=decision,
        valid=decision == "TRADE",
        reasons=tuple(reasons),
        checked_at=checked_at,
        expires_at=checked_at + expiry,
    )


def _no_trade(instrument: str, reason: str) -> OracleAnalysis:
    return OracleAnalysis(
        instrument=instrument,
        decision="NO_TRADE",
        technical_score=0.0,
        weighted_score=0.0,
        setup=None,
        confirmation=None,
        trade=None,
        risk=None,
        reasons=(reason, "technical-only diagnostic mode; no fundamental filters applied"),
    )
