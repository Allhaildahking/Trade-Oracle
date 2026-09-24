"""Deterministic entry, stop, target, and R:R construction."""

from __future__ import annotations

from decimal import Decimal

from app.models.confirmation import Confirmation5M
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate

MIN_RISK_REWARD = Decimal("2.5")


def construct_trade(
    *,
    setup: SetupCandidate,
    confirmation: Confirmation5M,
    min_risk_reward: Decimal = MIN_RISK_REWARD,
) -> TradeCandidate:
    """Construct a trade only from a confirmed 5M setup.

    Entry is the latest aligned 5M structure-break close. The stop uses the
    15M liquidity sweep extreme when available, because that level represents
    the setup invalidation. TP is derived from the requested minimum R:R.
    """
    if min_risk_reward <= 0:
        raise ValueError("min_risk_reward must be positive")
    if setup.status != "CANDIDATE":
        raise ValueError("setup must be a CANDIDATE")
    if confirmation.status != "CONFIRMED":
        raise ValueError("confirmation must be CONFIRMED")
    if setup.instrument != confirmation.instrument:
        raise ValueError("setup and confirmation instruments must match")
    if setup.direction not in {"BUY", "SELL"}:
        raise ValueError("setup direction must be BUY or SELL")
    if not confirmation.structure_events:
        raise ValueError("confirmation must contain an aligned structure event")

    event = confirmation.structure_events[-1]
    entry = event.price

    sweep = setup.sweep
    if sweep is None:
        return TradeCandidate(
            instrument=setup.instrument,
            direction=setup.direction,
            status="REJECTED",
            entry=None,
            stop_loss=None,
            take_profit=None,
            risk_distance=None,
            reward_distance=None,
            risk_reward=None,
            invalidation=None,
            reasons=("15M setup has no liquidity sweep to anchor invalidation",),
        )

    stop_loss = sweep.sweep_price
    if setup.direction == "BUY":
        risk_distance = entry - stop_loss
    else:
        risk_distance = stop_loss - entry

    if risk_distance <= 0:
        return TradeCandidate(
            instrument=setup.instrument,
            direction=setup.direction,
            status="REJECTED",
            entry=entry,
            stop_loss=stop_loss,
            take_profit=None,
            risk_distance=risk_distance,
            reward_distance=None,
            risk_reward=None,
            invalidation=stop_loss,
            reasons=("stop loss is on the wrong side of entry",),
        )

    reward_distance = risk_distance * min_risk_reward
    take_profit = (
        entry + reward_distance
        if setup.direction == "BUY"
        else entry - reward_distance
    )
    risk_reward = reward_distance / risk_distance

    return TradeCandidate(
        instrument=setup.instrument,
        direction=setup.direction,
        status="VALID",
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_distance=risk_distance,
        reward_distance=reward_distance,
        risk_reward=risk_reward,
        invalidation=stop_loss,
        reasons=(
            "entry anchored to latest confirmed 5M structure break",
            "stop anchored to 15M liquidity-sweep invalidation",
            f"target set at minimum {min_risk_reward}:1 R:R",
        ),
    )
