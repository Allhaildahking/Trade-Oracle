"""Deterministic market regime classification."""

from __future__ import annotations

from statistics import median

from app.models.market import Candle
from app.models.regime import RegimeKind, RegimeSnapshot


def _true_range(current: Candle, previous: Candle | None) -> float:
    if previous is None:
        return float(current.high - current.low)
    return max(
        float(current.high - current.low),
        abs(float(current.high - previous.close)),
        abs(float(current.low - previous.close)),
    )


def detect_regime(
    candles: list[Candle],
    *,
    lookback: int = 20,
    baseline_window: int = 50,
    high_volatility_ratio: float = 1.5,
    low_volatility_ratio: float = 0.7,
    trend_efficiency: float = 0.55,
    unstable: bool = False,
) -> RegimeSnapshot:
    """Classify a completed-candle sample into one mutually exclusive regime."""
    if lookback < 5:
        raise ValueError("lookback must be at least 5")
    if baseline_window < lookback:
        raise ValueError("baseline_window must be >= lookback")
    if not 0 < low_volatility_ratio < 1:
        raise ValueError("low_volatility_ratio must be between 0 and 1")
    if high_volatility_ratio <= 1:
        raise ValueError("high_volatility_ratio must be > 1")
    if not 0 < trend_efficiency <= 1:
        raise ValueError("trend_efficiency must be between 0 and 1")

    ordered = sorted(
        (candle for candle in candles if candle.is_complete),
        key=lambda candle: candle.timestamp,
    )
    if len(ordered) < baseline_window + lookback + 1:
        raise ValueError("not enough completed candles for regime detection")

    recent = ordered[-lookback:]
    baseline = ordered[-(baseline_window + lookback) : -lookback]

    recent_ranges = [
        _true_range(candle, recent[index - 1] if index else ordered[-lookback - 1])
        for index, candle in enumerate(recent)
    ]
    baseline_ranges = [
        _true_range(candle, baseline[index - 1] if index else ordered[-lookback - baseline_window - 1])
        for index, candle in enumerate(baseline)
    ]

    atr = sum(recent_ranges) / len(recent_ranges)
    baseline_atr = median(baseline_ranges)
    volatility_ratio = atr / baseline_atr if baseline_atr else float("inf")

    net_move = abs(float(recent[-1].close - recent[0].close))
    path = sum(
        abs(float(recent[index].close - recent[index - 1].close))
        for index in range(1, len(recent))
    )
    directional_efficiency = net_move / path if path else 0.0
    range_to_atr = (
        float(max(candle.high for candle in recent) - min(candle.low for candle in recent))
        / atr
        if atr
        else float("inf")
    )

    if unstable:
        regime: RegimeKind = "UNSTABLE"
    elif volatility_ratio >= high_volatility_ratio:
        regime = "HIGH_VOLATILITY"
    elif volatility_ratio <= low_volatility_ratio:
        regime = "LOW_VOLATILITY"
    elif directional_efficiency >= trend_efficiency and range_to_atr >= 2:
        regime = "TRENDING"
    else:
        regime = "RANGING"

    return RegimeSnapshot(
        instrument=recent[-1].instrument,
        timeframe=recent[-1].timeframe,
        regime=regime,
        atr=atr,
        baseline_atr=baseline_atr,
        volatility_ratio=volatility_ratio,
        directional_efficiency=directional_efficiency,
        range_to_atr=range_to_atr,
        sample_size=len(recent),
    )
