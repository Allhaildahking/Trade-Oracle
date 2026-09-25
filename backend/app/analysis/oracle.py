"""End-to-end deterministic Trade Oracle pair pipeline."""

from __future__ import annotations

from datetime import datetime

from app.analysis.confirmation_5m import confirm_5m
from app.analysis.decision import DecisionContext, decide
from app.analysis.risk import validate_trade
from app.analysis.setup import detect_setup_candidate
from app.analysis.structure import detect_structure
from app.analysis.trade import construct_trade
from app.models.confirmation import Confirmation5M
from app.models.fundamental import EconomicEvent, PairBias
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle, Quote
from app.models.oracle import OracleAnalysis
from app.models.setup import SetupCandidate

TECHNICAL_WEIGHTS = {
    "htf_structure": 0.20,
    "sweep": 0.15,
    "displacement": 0.15,
    "break_retest": 0.15,
    "confirmation_structure": 0.20,
    "confirmation_displacement": 0.15,
}


def analyze_pair(
    *,
    candles_4h: list[Candle],
    candles_1h: list[Candle],
    candles_15m: list[Candle],
    candles_5m: list[Candle],
    pair_bias: PairBias,
    liquidity_levels: tuple[LiquidityLevel, ...] = (),
    quote: Quote | None = None,
    economic_events: tuple[EconomicEvent, ...] = (),
    checked_at: datetime,
    duplicate_active: bool = False,
) -> OracleAnalysis:
    """Run one pair through the complete V1 decision chain.

    This function only analyzes. It never places orders or accesses a broker.
    """
    if checked_at.tzinfo is None:
        raise ValueError("checked_at must be timezone-aware")

    instrument = pair_bias.instrument
    _validate_candles(instrument, candles_4h, "4H")
    _validate_candles(instrument, candles_1h, "1H")
    _validate_candles(instrument, candles_15m, "15M")
    _validate_candles(instrument, candles_5m, "5M")

    htf_structure = (
        detect_structure(candles_4h),
        detect_structure(candles_1h),
    )
    setup = detect_setup_candidate(
        candles_15m,
        pair_bias=pair_bias,
        htf_structure=htf_structure,
        liquidity_levels=liquidity_levels,
    )

    technical_score = _setup_score(setup)

    if setup.status != "CANDIDATE":
        context = DecisionContext.from_pair_bias(
            pair_bias,
            technical_score=technical_score,
            setup=setup,
        )
        decision = decide(context)
        return OracleAnalysis(
            instrument=instrument,
            decision=decision,
            technical_score=technical_score,
            weighted_score=context.weighted_score,
            setup=setup,
            confirmation=None,
            trade=None,
            risk=None,
            reasons=setup.reasons,
        )

    confirmation = confirm_5m(
        candles_5m,
        setup=setup,
        liquidity_levels=liquidity_levels,
    )
    technical_score = _technical_score(setup, confirmation)

    trade = construct_trade(setup=setup, confirmation=confirmation)

    fundamental_aligned = (
        pair_bias.direction
        == setup.direction
        == confirmation.direction
        == trade.direction
    )

    risk = validate_trade(
        trade=trade,
        confirmation=confirmation,
        setup_regime=setup.regime.regime,
        fundamental_aligned=fundamental_aligned,
        checked_at=checked_at,
        quote=quote,
        economic_events=economic_events,
        duplicate_active=duplicate_active,
    )

    context = DecisionContext.from_pair_bias(
        pair_bias,
        technical_score=technical_score,
        setup=setup,
        confirmation=confirmation,
        trade=trade,
        risk=risk,
    )
    decision = decide(context)

    return OracleAnalysis(
        instrument=instrument,
        decision=decision,
        technical_score=technical_score,
        weighted_score=context.weighted_score,
        setup=setup,
        confirmation=confirmation,
        trade=trade,
        risk=risk,
        reasons=tuple(
            [*setup.reasons, *confirmation.reasons, *trade.reasons, *risk.reasons]
        ),
    )


def _setup_score(setup: SetupCandidate) -> float:
    score = 0.0
    if setup.structure_events:
        score += TECHNICAL_WEIGHTS["htf_structure"]
    if setup.sweep is not None:
        score += TECHNICAL_WEIGHTS["sweep"]
    if setup.displacement is not None:
        score += TECHNICAL_WEIGHTS["displacement"]
    if setup.break_retest is not None:
        score += TECHNICAL_WEIGHTS["break_retest"]
    return round(score, 4)


def _technical_score(setup: SetupCandidate, confirmation: Confirmation5M) -> float:
    score = _setup_score(setup)
    if confirmation.structure_events:
        score += TECHNICAL_WEIGHTS["confirmation_structure"]
    if confirmation.displacement is not None:
        score += TECHNICAL_WEIGHTS["confirmation_displacement"]
    return round(min(1.0, score), 4)


def _validate_candles(
    instrument: str,
    candles: list[Candle],
    timeframe: str,
) -> None:
    if not candles:
        raise ValueError(f"{timeframe} candles must not be empty")
    if any(candle.instrument != instrument for candle in candles):
        raise ValueError(f"{timeframe} candle instrument must match pair bias")
    if any(candle.timeframe != timeframe for candle in candles):
        raise ValueError(f"{timeframe} candles must use timeframe {timeframe}")
