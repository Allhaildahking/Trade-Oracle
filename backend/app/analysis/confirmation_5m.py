"""Deterministic 5M confirmation for 15M setup candidates."""

from __future__ import annotations

from app.analysis.displacement import detect_displacements
from app.analysis.liquidity_sweep import detect_liquidity_sweeps
from app.analysis.structure import detect_structure
from app.models.liquidity import LiquidityLevel
from app.models.market import Candle
from app.models.setup import SetupCandidate
from app.models.confirmation import Confirmation5M


def confirm_5m(
    candles_5m: list[Candle],
    *,
    setup: SetupCandidate,
    liquidity_levels: tuple[LiquidityLevel, ...] = (),
) -> Confirmation5M:
    """Confirm a directional 15M setup using completed 5M evidence.

    Confirmation requires a 5M structure break aligned with the setup and a
    directional displacement. A 5M liquidity sweep is supporting evidence, not
    a mandatory trigger.
    """
    if not candles_5m:
        raise ValueError("candles_5m must not be empty")

    instrument = candles_5m[0].instrument
    if setup.instrument != instrument:
        raise ValueError("setup instrument must match candles_5m")
    if setup.status != "CANDIDATE":
        raise ValueError("setup must be a CANDIDATE")

    desired = "BULLISH" if setup.direction == "BUY" else "BEARISH"
    structure = detect_structure(candles_5m)
    displacements = detect_displacements(candles_5m)
    sweeps = detect_liquidity_sweeps(candles_5m, liquidity_levels)

    aligned_events = tuple(
        event for event in structure.events if event.direction == desired
    )
    displacement = next(
        (item for item in reversed(displacements) if item.direction == desired),
        None,
    )
    sweep = next(
        (item for item in reversed(sweeps) if item.direction == desired),
        None,
    )

    reasons: list[str] = [
        f"15M setup direction: {setup.direction}",
        f"5M structure: {len(aligned_events)} aligned event(s)",
    ]
    if displacement:
        reasons.append("5M displacement confirmed")
    if sweep:
        reasons.append("5M liquidity sweep supports the setup")
    else:
        reasons.append("no aligned 5M liquidity sweep")

    confirmed = bool(aligned_events and displacement)

    if confirmed:
        reasons.append("5M structure and displacement confirm the 15M thesis")
        status = "CONFIRMED"
    else:
        reasons.append("5M confirmation is incomplete or conflicts with the 15M thesis")
        status = "REJECTED"

    return Confirmation5M(
        instrument=instrument,
        timeframe="5M",
        direction=setup.direction,
        status=status,
        structure_events=aligned_events,
        displacement=displacement,
        sweep=sweep,
        reasons=tuple(reasons),
    )
