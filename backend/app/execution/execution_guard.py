"""Fail-closed execution approval gate for broker order submission.

This module decides whether an Oracle analysis may be handed to an execution
adapter. It never sends orders and defaults to disabled execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.execution.position_sizing import PositionSize, calculate_position_size
from app.models.account import AccountSnapshot
from app.models.market import Quote
from app.models.oracle import OracleAnalysis
from app.models.symbol import SymbolSpec


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """Hard limits applied immediately before every order request."""

    enabled: bool = False
    require_demo_account: bool = True
    risk_percent: Decimal = Decimal("10.0")
    max_risk_percent: Decimal = Decimal("10.0")
    max_daily_loss_percent: Decimal = Decimal("20.0")
    reduced_risk_balance_threshold: Decimal = Decimal("30.0")
    reduced_risk_multiplier: Decimal = Decimal("0.5")
    max_open_positions: int = 1
    max_spread_to_risk: Decimal = Decimal("0.10")
    max_quote_age: timedelta = timedelta(seconds=10)
    allowed_instruments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not Decimal("0") < self.risk_percent <= self.max_risk_percent <= Decimal("10"):
            raise ValueError("risk must be positive and capped at 10 percent")
        if self.max_daily_loss_percent <= 0 or self.max_daily_loss_percent > 20:
            raise ValueError("max_daily_loss_percent must be in (0, 20]")
        if self.reduced_risk_balance_threshold <= 0:
            raise ValueError("reduced_risk_balance_threshold must be positive")
        if not Decimal("0") < self.reduced_risk_multiplier <= Decimal("1"):
            raise ValueError("reduced_risk_multiplier must be in (0, 1]")
        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1")
        if self.max_spread_to_risk < 0:
            raise ValueError("max_spread_to_risk must not be negative")
        if self.max_quote_age <= timedelta(0):
            raise ValueError("max_quote_age must be positive")


@dataclass(frozen=True, slots=True)
class ExecutionApproval:
    """Auditable outcome of the execution gate."""

    approved: bool
    instrument: str
    volume: Decimal | None
    estimated_loss: Decimal | None
    risk_budget: Decimal | None
    reasons: tuple[str, ...]


def approve_execution(
    *,
    analysis: OracleAnalysis,
    account: AccountSnapshot,
    quote: Quote,
    symbol_spec: SymbolSpec,
    now: datetime,
    open_positions: int,
    daily_realized_loss: Decimal,
    policy: ExecutionPolicy,
) -> ExecutionApproval:
    """Approve a proposed trade only when every execution invariant passes.

    `daily_realized_loss` is a positive account-currency amount representing
    the absolute realized loss since the broker's trading-day boundary.
    The caller must obtain it from broker history, not a process-local counter.
    """
    reasons: list[str] = []
    trade = analysis.trade
    instrument = analysis.instrument

    def reject(reason: str) -> ExecutionApproval:
        reasons.append(reason)
        return ExecutionApproval(
            approved=False,
            instrument=instrument,
            volume=None,
            estimated_loss=None,
            risk_budget=None,
            reasons=tuple(reasons),
        )

    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    if open_positions < 0:
        raise ValueError("open_positions must not be negative")
    if daily_realized_loss < 0:
        raise ValueError("daily_realized_loss must not be negative")

    if not policy.enabled:
        return reject("execution is disabled by policy")
    if instrument not in policy.allowed_instruments:
        return reject("instrument is not allowlisted")
    if not account.is_demo and policy.require_demo_account:
        return reject("live account rejected: demo account required")
    if account.equity <= 0:
        return reject("account equity is unavailable or invalid")
    if account.currency.upper() != "USD":
        return reject("balance-based risk tiers require a USD-denominated account")
    if open_positions >= policy.max_open_positions:
        return reject("maximum open-position limit reached")
    risk_multiplier = (
        policy.reduced_risk_multiplier
        if account.equity >= policy.reduced_risk_balance_threshold
        else Decimal("1")
    )
    effective_risk_percent = policy.risk_percent * risk_multiplier
    effective_daily_loss_percent = policy.max_daily_loss_percent * risk_multiplier

    if daily_realized_loss >= account.equity * effective_daily_loss_percent / Decimal("100"):
        return reject("daily realized-loss limit reached")
    if analysis.decision != "TRADE":
        return reject(f"Oracle decision is {analysis.decision}, not TRADE")
    if trade is None or trade.status != "VALID":
        return reject("valid trade candidate is missing")
    if trade.instrument != instrument or symbol_spec.instrument != instrument:
        return reject("trade, analysis, and broker symbol do not match")
    if trade.entry is None or trade.stop_loss is None or trade.take_profit is None:
        return reject("entry, stop loss, and take profit are required")
    if trade.risk_reward is None or trade.risk_reward < Decimal("2.5"):
        return reject("trade does not meet the 1:2.5 minimum reward/risk")
    if analysis.risk is None or not analysis.risk.valid or analysis.risk.decision != "TRADE":
        return reject("Oracle risk validation is missing or not approved")
    if analysis.risk.expires_at is None or analysis.risk.expires_at <= now:
        return reject("Oracle risk validation has expired")
    if quote.instrument != instrument or quote.bid is None or quote.ask is None:
        return reject("current quote is missing or for the wrong instrument")
    if quote.timestamp.tzinfo is None:
        return reject("quote timestamp must be timezone-aware")
    quote_age = now - quote.timestamp
    if quote_age < timedelta(seconds=-2) or quote_age > policy.max_quote_age:
        return reject("quote is stale or timestamp is in the future")
    if quote.bid <= 0 or quote.ask < quote.bid:
        return reject("quote bid/ask is invalid")
    if trade.risk_distance is None or trade.risk_distance <= 0:
        return reject("trade risk distance is invalid")
    spread = quote.ask - quote.bid
    if spread / trade.risk_distance > policy.max_spread_to_risk:
        return reject("spread exceeds the configured risk-distance threshold")

    size: PositionSize = calculate_position_size(
        equity=account.equity,
        risk_percent=effective_risk_percent,
        direction=trade.direction,
        entry=trade.entry,
        stop_loss=trade.stop_loss,
        spec=symbol_spec,
    )
    if not size.accepted or size.volume is None:
        return reject(f"position sizing rejected: {size.reason}")

    reasons.extend(
        (
            "Oracle decision and risk validation passed",
            (
                f"effective risk is {effective_risk_percent}% per trade; "
                f"daily loss cutoff is {effective_daily_loss_percent}%"
            ),
            "account, instrument, quote, and position limits passed",
            size.reason,
        )
    )
    return ExecutionApproval(
        approved=True,
        instrument=instrument,
        volume=size.volume,
        estimated_loss=size.estimated_loss,
        risk_budget=size.risk_budget,
        reasons=tuple(reasons),
    )
