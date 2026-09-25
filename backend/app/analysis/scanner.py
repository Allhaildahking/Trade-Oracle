"""Deterministic six-pair market scanner."""

from __future__ import annotations

from app.analysis.decision import DecisionContext, decide
from app.core.constants import CANDIDATE_INSTRUMENTS, CORE_INSTRUMENTS
from app.models.market_scan import MarketScan, PairAssessment
from app.analysis.rotation import RotationDecision

DEFAULT_ACTIVE_INSTRUMENTS = CORE_INSTRUMENTS + ("USDCAD",)


def active_universe(rotation: RotationDecision) -> tuple[str, ...]:
    """Build the six-pair scanner universe from the current rotation decision."""
    if rotation.active_instrument not in CANDIDATE_INSTRUMENTS:
        raise ValueError(f"invalid rotated sixth pair: {rotation.active_instrument}")
    return CORE_INSTRUMENTS + (rotation.active_instrument,)
_DECISION_PRIORITY = {"TRADE": 5, "WATCH": 4, "WAIT": 3, "NO_TRADE": 2, "BLOCKED": 1}


def scan(
    contexts: tuple[DecisionContext, ...],
    *,
    active_instruments: tuple[str, ...] = DEFAULT_ACTIVE_INSTRUMENTS,
) -> MarketScan:
    """Evaluate and rank the active universe without overriding decisions."""
    _validate_universe(active_instruments)
    by_instrument = _index_contexts(contexts)
    missing = tuple(item for item in active_instruments if item not in by_instrument)
    if missing:
        raise ValueError(f"missing scanner contexts: {', '.join(missing)}")

    assessments = tuple(
        _assessment(instrument, by_instrument[instrument])
        for instrument in active_instruments
    )
    ranked = tuple(sorted(assessments, key=_ranking_key, reverse=True))
    return MarketScan(
        assessments=assessments,
        ranked=ranked,
        active_instruments=active_instruments,
    )


def _assessment(instrument: str, context: DecisionContext) -> PairAssessment:
    decision = decide(context)
    trade = context.trade
    direction = trade.direction if trade is not None else None
    risk_reward = (
        float(trade.risk_reward)
        if trade is not None and trade.risk_reward is not None
        else None
    )
    return PairAssessment(
        instrument=instrument,
        decision=decision,
        weighted_score=context.weighted_score,
        risk_reward=risk_reward,
        direction=direction,
        reasons=(f"decision={decision}", f"weighted_score={context.weighted_score:.3f}"),
    )


def _ranking_key(candidate: PairAssessment) -> tuple[int, float, float, str]:
    return (
        _DECISION_PRIORITY[candidate.decision],
        candidate.weighted_score,
        candidate.risk_reward or 0.0,
        candidate.instrument,
    )


def _index_contexts(contexts: tuple[DecisionContext, ...]) -> dict[str, DecisionContext]:
    indexed: dict[str, DecisionContext] = {}
    for context in contexts:
        instrument = _context_instrument(context)
        if instrument in indexed:
            raise ValueError(f"duplicate scanner context: {instrument}")
        indexed[instrument] = context
    return indexed


def _context_instrument(context: DecisionContext) -> str:
    for evidence in (context.trade, context.confirmation, context.setup, context.risk):
        if evidence is not None:
            return evidence.instrument
    raise ValueError("scanner context must contain an instrument-bearing result")


def _validate_universe(active_instruments: tuple[str, ...]) -> None:
    if len(active_instruments) != 6:
        raise ValueError("scanner requires exactly 6 active instruments")
    if len(set(active_instruments)) != 6:
        raise ValueError("active scanner instruments must be unique")
    allowed = set(CORE_INSTRUMENTS) | set(CANDIDATE_INSTRUMENTS)
    invalid = tuple(item for item in active_instruments if item not in allowed)
    if invalid:
        raise ValueError(f"unsupported scanner instruments: {', '.join(invalid)}")
