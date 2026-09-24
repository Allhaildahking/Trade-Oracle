"""Market-data quality checks. Bad data must never silently reach analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.models.market import Candle


@dataclass(frozen=True, slots=True)
class DataIssue:
    code: str
    message: str
    timestamp: object | None = None


def validate_candles(
    candles: list[Candle],
    *,
    expected_interval: timedelta | None = None,
) -> list[DataIssue]:
    issues: list[DataIssue] = []
    ordered = sorted(candles, key=lambda candle: candle.timestamp)

    if len(ordered) != len({c.timestamp for c in ordered}):
        issues.append(DataIssue("DUPLICATE_TIMESTAMP", "Duplicate candle timestamps detected."))

    for previous, current in zip(ordered, ordered[1:], strict=True):
        if current.timestamp <= previous.timestamp:
            issues.append(
                DataIssue(
                    "OUT_OF_ORDER",
                    "Candle timestamps are not strictly increasing.",
                    current.timestamp,
                )
            )
        if expected_interval is not None:
            gap = current.timestamp - previous.timestamp
            if gap > expected_interval * 2:
                issues.append(
                    DataIssue(
                        "MISSING_BARS",
                        f"Gap of {gap} exceeds expected interval.",
                        current.timestamp,
                    )
                )

    for candle in ordered:
        if candle.high < max(candle.open, candle.close, candle.low):
            issues.append(
                DataIssue("INVALID_HIGH", "High is below an OHLC value.", candle.timestamp)
            )
        if candle.low > min(candle.open, candle.close, candle.high):
            issues.append(
                DataIssue("INVALID_LOW", "Low is above an OHLC value.", candle.timestamp)
            )
        if min(candle.open, candle.high, candle.low, candle.close) <= 0:
            issues.append(
                DataIssue(
                    "NON_POSITIVE_PRICE",
                    "OHLC prices must be positive.",
                    candle.timestamp,
                )
            )

    return issues


def assert_valid_candles(
    candles: list[Candle],
    *,
    expected_interval: timedelta | None = None,
) -> None:
    issues = validate_candles(candles, expected_interval=expected_interval)
    if issues:
        summary = "; ".join(f"{issue.code}: {issue.message}" for issue in issues[:5])
        raise ValueError(summary)
