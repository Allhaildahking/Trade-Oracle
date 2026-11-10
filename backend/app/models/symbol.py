"""Broker symbol metadata required for safe, broker-aware position sizing."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class SymbolSpec:
    """Trading constraints and tick economics reported by the connected broker."""

    instrument: str
    trade_tick_size: Decimal
    trade_tick_value_loss: Decimal
    volume_min: Decimal
    volume_max: Decimal
    volume_step: Decimal
    contract_size: Decimal

    def __post_init__(self) -> None:
        positive = (
            "trade_tick_size",
            "trade_tick_value_loss",
            "volume_min",
            "volume_max",
            "volume_step",
            "contract_size",
        )
        for field_name in positive:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max must be greater than or equal to volume_min")
