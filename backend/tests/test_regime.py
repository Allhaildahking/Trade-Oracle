from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.analysis.regime import detect_regime
from app.models.market import Candle

def candle(index: int, close: str, *, spread: str = "0.0010") -> Candle:
    timestamp = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
    close_price = Decimal(close)
    half = Decimal(spread) / 2
    return Candle(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=timestamp,
        open=close_price,
        high=close_price + half,
        low=close_price - half,
        close=close_price,
    )


def sample(
    *,
    baseline_spread: str = "0.0010",
    recent_spread: str = "0.0010",
    trend: bool = False,
) -> list[Candle]:
    values = [Decimal("1.1000")] * 71
    for index in range(51, 71):
        if trend:
            values[index] = Decimal("1.1000") + Decimal("0.0002") * (index - 30)
    return [
        candle(
            index,
            str(values[index]),
            spread=recent_spread if index >= 51 else baseline_spread,
        )
        for index in range(71)
    ]


def test_detects_trending_regime() -> None:
    result = detect_regime(sample(trend=True))
    assert result.regime == "TRENDING"


def test_detects_ranging_regime() -> None:
    result = detect_regime(sample())
    assert result.regime == "RANGING"


def test_detects_high_volatility() -> None:
    result = detect_regime(sample(recent_spread="0.0030"))
    assert result.regime == "HIGH_VOLATILITY"


def test_detects_low_volatility() -> None:
    result = detect_regime(sample(recent_spread="0.0005"))
    assert result.regime == "LOW_VOLATILITY"


def test_unstable_overrides_other_classification() -> None:
    result = detect_regime(sample(trend=True), unstable=True)
    assert result.regime == "UNSTABLE"


def test_requires_enough_history() -> None:
    with pytest.raises(ValueError, match="not enough"):
        detect_regime(sample()[:60])
