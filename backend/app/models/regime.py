"""Domain models for deterministic market regime classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RegimeKind = Literal["TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNSTABLE"]


@dataclass(frozen=True, slots=True)
class RegimeSnapshot:
    instrument: str
    timeframe: str
    regime: RegimeKind
    atr: float
    baseline_atr: float
    volatility_ratio: float
    directional_efficiency: float
    range_to_atr: float
    sample_size: int
