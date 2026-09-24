from datetime import UTC, datetime, timedelta

import pytest

from app.analysis.signal_lifecycle import update_signal
from app.models.signal import Direction, Signal, SignalState

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def make_signal(
    *,
    direction: Direction = Direction.BUY,
    state: SignalState = SignalState.WATCH,
    expiry_at: datetime | None = None,
) -> Signal:
    return Signal(
        instrument="EURUSD",
        direction=direction,
        entry=100.0,
        stop_loss=98.0 if direction == Direction.BUY else 102.0,
        take_profit=105.0 if direction == Direction.BUY else 95.0,
        confidence=0.8,
        created_at=NOW,
        expiry_at=expiry_at,
        state=state,
    )


def test_watch_stays_watch_before_entry() -> None:
    result = update_signal(make_signal(), current_price=99.0, checked_at=NOW)
    assert result.state == SignalState.WATCH


def test_watch_becomes_active_at_entry() -> None:
    result = update_signal(make_signal(), current_price=100.0, checked_at=NOW)
    assert result.state == SignalState.ACTIVE


def test_watch_expires() -> None:
    signal = make_signal(expiry_at=NOW + timedelta(minutes=30))
    result = update_signal(
        signal,
        current_price=99.0,
        checked_at=NOW + timedelta(minutes=31),
    )
    assert result.state == SignalState.EXPIRED


def test_active_reaches_breakeven_at_one_r() -> None:
    signal = make_signal(state=SignalState.ACTIVE)
    result = update_signal(signal, current_price=102.0, checked_at=NOW)
    assert result.state == SignalState.BREAKEVEN


def test_active_hits_take_profit() -> None:
    signal = make_signal(state=SignalState.ACTIVE)
    result = update_signal(signal, current_price=105.0, checked_at=NOW)
    assert result.state == SignalState.TP_HIT


def test_active_hits_original_stop() -> None:
    signal = make_signal(state=SignalState.ACTIVE)
    result = update_signal(signal, current_price=98.0, checked_at=NOW)
    assert result.state == SignalState.INVALIDATED
    assert result.invalidation_reason == "original stop loss was hit"


def test_breakeven_return_to_entry_invalidates() -> None:
    signal = make_signal(state=SignalState.BREAKEVEN)
    result = update_signal(signal, current_price=100.0, checked_at=NOW)
    assert result.state == SignalState.INVALIDATED
    assert result.invalidation_reason == "breakeven stop was hit"


def test_thesis_invalidation_is_terminal() -> None:
    signal = make_signal(state=SignalState.ACTIVE)
    result = update_signal(
        signal,
        current_price=101.0,
        checked_at=NOW,
        thesis_valid=False,
    )
    assert result.state == SignalState.INVALIDATED


def test_sell_direction_transitions() -> None:
    signal = make_signal(direction=Direction.SELL)
    active = update_signal(signal, current_price=100.0, checked_at=NOW)
    assert active.state == SignalState.ACTIVE

    breakeven = update_signal(active, current_price=98.0, checked_at=NOW)
    assert breakeven.state == SignalState.BREAKEVEN

    target = update_signal(breakeven, current_price=95.0, checked_at=NOW)
    assert target.state == SignalState.TP_HIT


def test_terminal_signal_does_not_reopen() -> None:
    signal = make_signal(state=SignalState.TP_HIT)
    result = update_signal(signal, current_price=98.0, checked_at=NOW)
    assert result is signal


def test_naive_timestamps_are_rejected() -> None:
    signal = make_signal()
    with pytest.raises(ValueError, match="checked_at"):
        update_signal(signal, current_price=100.0, checked_at=datetime(2026, 9, 24, 12))


def test_invalid_prices_are_rejected() -> None:
    signal = make_signal()
    with pytest.raises(ValueError, match="current_price"):
        update_signal(signal, current_price=0.0, checked_at=NOW)
