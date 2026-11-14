"""Deterministic position sizing using live broker tick economics."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from app.models.symbol import SymbolSpec
from app.models.trade import TradeDirection

MAX_RISK_PERCENT = Decimal("10")


@dataclass(frozen=True, slots=True)
class PositionSize:
    accepted: bool
    volume: Decimal | None
    risk_budget: Decimal
    estimated_loss: Decimal | None
    loss_per_lot: Decimal | None
    reason: str


def calculate_position_size(
    *,
    equity: Decimal,
    risk_percent: Decimal,
    direction: TradeDirection,
    entry: Decimal,
    stop_loss: Decimal,
    spec: SymbolSpec,
) -> PositionSize:
    """Size down to the broker's volume step; never round risk upward.

    Tick value is the broker-reported loss value for one tick at one lot.
    A result below the broker minimum is rejected, never rounded up to minimum.
    """
    if equity <= 0:
        raise ValueError("equity must be positive")
    if direction not in ("BUY", "SELL"):
        raise ValueError("direction must be BUY or SELL")
    if not Decimal("0") < risk_percent <= MAX_RISK_PERCENT:
        raise ValueError("risk_percent must be greater than 0 and at most 10")
    if entry <= 0 or stop_loss <= 0:
        raise ValueError("entry and stop_loss must be positive")
    if direction == "BUY" and stop_loss >= entry:
        raise ValueError("BUY stop_loss must be below entry")
    if direction == "SELL" and stop_loss <= entry:
        raise ValueError("SELL stop_loss must be above entry")

    budget = equity * risk_percent / Decimal("100")
    distance = abs(entry - stop_loss)
    loss_per_lot = (distance / spec.trade_tick_size) * spec.trade_tick_value_loss
    if loss_per_lot <= 0:
        raise ValueError("calculated loss per lot must be positive")

    raw_volume = budget / loss_per_lot
    steps = (raw_volume / spec.volume_step).to_integral_value(rounding=ROUND_DOWN)
    volume = steps * spec.volume_step

    if volume < spec.volume_min:
        minimum_loss = spec.volume_min * loss_per_lot
        return PositionSize(
            accepted=False,
            volume=None,
            risk_budget=budget,
            estimated_loss=minimum_loss,
            loss_per_lot=loss_per_lot,
            reason=(
                "minimum broker volume exceeds the risk budget; "
                "trade rejected rather than increasing risk"
            ),
        )

    if volume > spec.volume_max:
        max_steps = (spec.volume_max / spec.volume_step).to_integral_value(
            rounding=ROUND_DOWN
        )
        volume = max_steps * spec.volume_step

    estimated_loss = volume * loss_per_lot
    if estimated_loss > budget:
        return PositionSize(
            accepted=False,
            volume=None,
            risk_budget=budget,
            estimated_loss=estimated_loss,
            loss_per_lot=loss_per_lot,
            reason="rounded volume would exceed the risk budget",
        )

    return PositionSize(
        accepted=True,
        volume=volume,
        risk_budget=budget,
        estimated_loss=estimated_loss,
        loss_per_lot=loss_per_lot,
        reason="position size fits the risk budget and broker volume constraints",
    )
