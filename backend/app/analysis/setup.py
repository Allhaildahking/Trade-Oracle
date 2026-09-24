"""Deterministic 15M setup candidate detection."""

from __future__ import annotations

from decimal import Decimal

from app.analysis.break_retest import detect_break_retests
from app.analysis.displacement import detect_displacements
from app.analysis.liquidity_sweep import detect_liquidity_sweeps
from app.analysis.regime import detect_regime
from app.analysis.structure import detect_structure
from app.models.fundamental import PairBias
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle
from app.models.setup import SetupCandidate
from app.models.structure import StructureSnapshot


def detect_setup_candidate(
    candles_15m: list[Candle],
    *,
    pair_bias: PairBias,
    htf_structure: tuple[StructureSnapshot, ...] = (),
    liquidity_levels: tuple[LiquidityLevel, ...] = (),
) -> SetupCandidate:
    """Combine fundamental bias and 15M evidence into a setup candidate.

    This layer does not calculate entry, stop, target, or risk. It only decides
    whether the available evidence forms a coherent directional setup.
    """
    if not candles_15m:
        raise ValueError("candles_15m must not be empty")

    instrument = candles_15m[0].instrument
    if pair_bias.instrument != instrument:
        raise ValueError("pair_bias instrument must match candles_15m")

    regime = detect_regime(candles_15m)
    structure_15m = detect_structure(candles_15m)
    sweeps = detect_liquidity_sweeps(candles_15m, liquidity_levels)
    displacements = detect_displacements(candles_15m)
    break_retests = detect_break_retests(
        candles_15m,
        levels=tuple(event.broken_swing.price for event in structure_15m.events),
        tolerance=Decimal("0"),
    )

    reasons: list[str] = []
    if pair_bias.direction == "NEUTRAL":
        reasons.append("fundamental bias is neutral")
    else:
        reasons.append(f"fundamental bias: {pair_bias.direction}")

    htf_directions = {
        event.direction
        for snapshot in htf_structure
        for event in snapshot.events[-3:]
    }
    if htf_directions:
        reasons.append(f"HTF structure: {', '.join(sorted(htf_directions))}")
    else:
        reasons.append("HTF structure has no confirmed recent event")

    if regime.regime == "UNSTABLE":
        reasons.append("market regime is unstable")
    else:
        reasons.append(f"15M regime: {regime.regime}")

    desired_direction = (
        "BULLISH" if pair_bias.direction == "BUY" else "BEARISH" if pair_bias.direction == "SELL" else None
    )

    matching_sweep = next(
        (item for item in reversed(sweeps) if item.direction == desired_direction),
        None,
    )
    matching_displacement = next(
        (item for item in reversed(displacements) if item.direction == desired_direction),
        None,
    )
    matching_break_retest = next(
        (
            item
            for item in reversed(break_retests)
            if item.direction == (
                "BULLISH" if pair_bias.direction == "BUY" else "BEARISH"
            )
        ),
        None,
    )

    if matching_sweep:
        reasons.append("15M liquidity sweep confirmed")
    if matching_displacement:
        reasons.append("15M displacement confirmed")
    if matching_break_retest:
        reasons.append("15M break and retest confirmed")

    structure_aligned = any(
        event.direction == desired_direction
        for snapshot in htf_structure
        for event in snapshot.events[-3:]
    )
    technical_complete = all(
        (matching_sweep, matching_displacement, matching_break_retest)
    )

    accepted = (
        pair_bias.direction in {"BUY", "SELL"}
        and structure_aligned
        and regime.regime not in {"UNSTABLE", "HIGH_VOLATILITY"}
        and technical_complete
    )

    if accepted:
        reasons.append("fundamental, HTF, regime, and 15M evidence align")
        status = "CANDIDATE"
    else:
        reasons.append("setup evidence is incomplete or conflicting")
        status = "REJECTED"

    return SetupCandidate(
        instrument=instrument,
        timeframe="15M",
        direction=pair_bias.direction,
        status=status,
        fundamental_score=str(pair_bias.score),
        regime=regime,
        structure_events=structure_15m.events,
        sweep=matching_sweep,
        displacement=matching_displacement,
        break_retest=matching_break_retest,
        reasons=tuple(reasons),
    )
