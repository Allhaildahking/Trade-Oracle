"""Safe account details exposed by the connected broker terminal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AccountSnapshot:
    equity: Decimal
    currency: str
    is_demo: bool
    leverage: int
