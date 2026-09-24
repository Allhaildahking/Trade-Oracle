"""Deterministic signal-state transitions for live and shadow monitoring."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.models.signal import Direction, Signal, SignalState

BREAKEVEN_TRIGGER_R = 1.0
TERMINAL_STATES = {
    SignalState.TP_HIT,
    SignalState.INVALIDATED,
    SignalState.EXPIRED,
}


def update_signal(
    signal: Signal,
    *,
    current_price: float,
    checked_at: datetime,
    thesis_valid: bool = True,
) -> Signal:
    """Advance one signal by one observed market-price snapshot.

    The function never executes trades or changes broker state. A signal becomes
    BREAKEVEN at +1R; after that, a return to entry is treated as a BE stop hit.
    """
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    if checked_at.tzinfo is None:
        raise ValueError("checked_at must be timezone-aware")
    if signal.created_at.tzinfo is None:
        raise ValueError("signal.created_at must be timezone-aware")
    if signal.expiry_at is not None and signal.expiry_at.tzinfo is None:
        raise ValueError("signal.expiry_at must be timezone-aware")
    if signal.entry <= 0 or signal.stop_loss <= 0 or signal.take_profit <= 0:
        raise ValueError("signal prices must be positive")
    if signal.risk_distance <= 0:
        raise ValueError("signal risk distance must be positive")

    if signal.state in TERMINAL_STATES:
        return signal

    if signal.expiry_at is not None and checked_at >= signal.expiry_at:
        return replace(
            signal,
            state=SignalState.EXPIRED,
            updated_at=checked_at,
            invalidation_reason="signal expired before reaching a terminal price outcome",
        )

    if signal.state == SignalState.WATCH:
        if not thesis_valid:
            return replace(
                signal,
                state=SignalState.INVALIDATED,
                updated_at=checked_at,
                invalidation_reason="trade thesis was invalidated before activation",
            )
        if _entry_reached(signal, current_price):
            return replace(signal, state=SignalState.ACTIVE, updated_at=checked_at)
        return replace(signal, updated_at=checked_at)

    if signal.state == SignalState.ACTIVE:
        if _take_profit_hit(signal, current_price):
            return replace(signal, state=SignalState.TP_HIT, updated_at=checked_at)
        if _stop_hit(signal, current_price):
            return replace(
                signal,
                state=SignalState.INVALIDATED,
                updated_at=checked_at,
                invalidation_reason="original stop loss was hit",
            )
        if not thesis_valid:
            return replace(
                signal,
                state=SignalState.INVALIDATED,
                updated_at=checked_at,
                invalidation_reason="trade thesis was invalidated while active",
            )
        if _one_r_reached(signal, current_price):
            return replace(signal, state=SignalState.BREAKEVEN, updated_at=checked_at)
        return replace(signal, updated_at=checked_at)

    if signal.state == SignalState.BREAKEVEN:
        if _take_profit_hit(signal, current_price):
            return replace(signal, state=SignalState.TP_HIT, updated_at=checked_at)
        if _breakeven_stop_hit(signal, current_price):
            return replace(
                signal,
                state=SignalState.INVALIDATED,
                updated_at=checked_at,
                invalidation_reason="breakeven stop was hit",
            )
        if not thesis_valid:
            return replace(
                signal,
                state=SignalState.INVALIDATED,
                updated_at=checked_at,
                invalidation_reason="trade thesis was invalidated after breakeven",
            )
        return replace(signal, updated_at=checked_at)

    raise ValueError(f"unsupported signal state: {signal.state}")


def _entry_reached(signal: Signal, price: float) -> bool:
    if signal.direction == Direction.BUY:
        return price >= signal.entry
    return price <= signal.entry


def _take_profit_hit(signal: Signal, price: float) -> bool:
    if signal.direction == Direction.BUY:
        return price >= signal.take_profit
    return price <= signal.take_profit


def _stop_hit(signal: Signal, price: float) -> bool:
    if signal.direction == Direction.BUY:
        return price <= signal.stop_loss
    return price >= signal.stop_loss


def _one_r_reached(signal: Signal, price: float) -> bool:
    if signal.direction == Direction.BUY:
        return price >= signal.entry + signal.risk_distance * BREAKEVEN_TRIGGER_R
    return price <= signal.entry - signal.risk_distance * BREAKEVEN_TRIGGER_R


def _breakeven_stop_hit(signal: Signal, price: float) -> bool:
    if signal.direction == Direction.BUY:
        return price <= signal.entry
    return price >= signal.entry
