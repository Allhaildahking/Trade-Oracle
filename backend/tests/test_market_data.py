from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.data.repository import InMemoryCandleRepository
from app.data.validation import validate_candles
from app.models.market import Candle


def candle(minute: int, *, high: str = "1.2") -> Candle:
    return Candle(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
        open=Decimal("1.1"),
        high=Decimal(high),
        low=Decimal("1.0"),
        close=Decimal("1.15"),
    )


def test_repository_deduplicates_timestamps() -> None:
    repo = InMemoryCandleRepository()
    assert repo.upsert([candle(0), candle(0)]) == 1
    assert len(repo.get("EURUSD", "5M")) == 1


def test_validation_detects_large_gaps() -> None:
    issues = validate_candles(
        [candle(0), candle(15)],
        expected_interval=timedelta(minutes=5),
    )
    assert any(issue.code == "MISSING_BARS" for issue in issues)


def test_validation_rejects_invalid_prices() -> None:
    issues = validate_candles([candle(0, high="0.9")])
    assert any(issue.code == "INVALID_HIGH" for issue in issues)


def test_repository_returns_latest_limit() -> None:
    repo = InMemoryCandleRepository()
    repo.upsert([candle(0), candle(1), candle(2)])
    result = repo.get("EURUSD", "5M", limit=2)
    assert [item.timestamp.minute for item in result] == [1, 2]
