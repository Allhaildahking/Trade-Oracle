"""Deterministic risk and validation gate before a signal becomes actionable."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from app.models.confirmation import Confirmation5M
from app.models.fundamental import EconomicEvent
from app.models.market import Quote
from app.models.risk import RiskValidation
from app.models.trade import TradeCandidate

CRITICAL_IMPORTANCE = {"HIGH", "CRITICAL"}
DEFAULT_EXPIRY = timedelta(minutes=30)


def validate_trade(
    *,
    trade: TradeCandidate,
    confirmation: Confirmation5M,
    setup_regime: str,
    fundamental_aligned: bool,
    checked_at: datetime,
    quote: Quote | None = None,
    economic_events: tuple[EconomicEvent, ...] = (),
    duplicate_active: bool = False,
    expiry: timedelta = DEFAULT_EXPIRY,
    news_blocking_minutes: int = 30,
    max_spread_ratio: Decimal = Decimal("0.10"),
) -> RiskValidation:
    """Apply deterministic safety gates without executing a trade.

    Missing economic-calendar data is treated as blocked rather than safe.
    """
    if expiry <= timedelta(0):
        raise ValueError("expiry must be positive")
    if news_blocking_minutes < 0:
        raise ValueError("news_blocking_minutes must not be negative")
    if max_spread_ratio < 0:
        raise ValueError("max_spread_ratio must not be negative")
    if checked_at.tzinfo is None:
        raise ValueError("checked_at must be timezone-aware")

    reasons: list[str] = []
    blocking = False
    waiting = False

    if trade.status != "VALID":
        reasons.append("trade candidate is not valid")
        blocking = True
    elif trade.risk_reward is None or trade.risk_reward < Decimal("2.5"):
        reasons.append("risk/reward is below the 2.5 minimum")
        blocking = True
    else:
        reasons.append("risk/reward meets the 2.5 minimum")

    if confirmation.status != "CONFIRMED":
        reasons.append("5M confirmation is not confirmed")
        blocking = True
    else:
        reasons.append("5M confirmation is confirmed")

    if setup_regime in {"UNSTABLE", "HIGH_VOLATILITY"}:
        reasons.append(f"regime {setup_regime} is incompatible with a normal trade")
        blocking = True
    else:
        reasons.append(f"regime {setup_regime} passes the regime gate")

    if not fundamental_aligned:
        reasons.append("fundamental and technical direction are in conflict")
        blocking = True
    else:
        reasons.append("fundamental and technical direction are aligned")

    if quote is None:
        reasons.append("live quote/spread is unavailable")
        waiting = True
    elif quote.instrument != trade.instrument:
        reasons.append("quote instrument does not match trade")
        blocking = True
    elif quote.bid is None or quote.ask is None or quote.ask < quote.bid:
        reasons.append("quote bid/ask is invalid")
        blocking = True
    else:
        spread = quote.ask - quote.bid
        if trade.risk_distance is None or trade.risk_distance <= 0:
            reasons.append("trade risk distance is unavailable")
            blocking = True
        elif spread / trade.risk_distance > max_spread_ratio:
            reasons.append("spread is too large relative to trade risk")
            blocking = True
        else:
            reasons.append("spread is acceptable relative to trade risk")

    if not economic_events:
        reasons.append("economic-calendar context is unavailable")
        blocking = True
    else:
        nearby = tuple(
            event
            for event in economic_events
            if event.importance.upper() in CRITICAL_IMPORTANCE
            and abs((event.timestamp - checked_at).total_seconds())
            <= news_blocking_minutes * 60
            and event.currency in _instrument_currencies(trade.instrument)
        )
        if nearby:
            reasons.append("high-impact economic event is inside the news block window")
            blocking = True
        else:
            reasons.append("no relevant high-impact event is inside the news block window")

    if duplicate_active:
        reasons.append("an active duplicate signal already exists")
        blocking = True
    else:
        reasons.append("no active duplicate signal detected")

    expires_at = checked_at + expiry
    reasons.append(f"signal validation expires at {expires_at.isoformat()}")

    if blocking:
        decision: RiskValidation = RiskValidation(
            instrument=trade.instrument,
            decision="BLOCKED",
            valid=False,
            reasons=tuple(reasons),
            checked_at=checked_at,
            expires_at=expires_at,
        )
    elif waiting:
        decision = RiskValidation(
            instrument=trade.instrument,
            decision="WAIT",
            valid=False,
            reasons=tuple(reasons),
            checked_at=checked_at,
            expires_at=expires_at,
        )
    else:
        decision = RiskValidation(
            instrument=trade.instrument,
            decision="TRADE",
            valid=True,
            reasons=tuple(reasons),
            checked_at=checked_at,
            expires_at=expires_at,
        )

    return decision


def _instrument_currencies(instrument: str) -> tuple[str, ...]:
    if instrument == "XAUUSD":
        return ("XAU", "USD")
    if len(instrument) == 6:
        return (instrument[:3], instrument[3:])
    return (instrument,)
