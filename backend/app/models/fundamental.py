"""Canonical fundamental and economic-calendar models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class EconomicEvent:
    event_id: str
    country: str
    currency: str
    title: str
    timestamp: datetime
    importance: str
    actual: Decimal | None = None
    forecast: Decimal | None = None
    previous: Decimal | None = None
    unit: str | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class NewsItem:
    news_id: str
    timestamp: datetime
    title: str
    summary: str
    source_name: str
    url: str | None
    currencies: tuple[str, ...] = ()
    sentiment_label: str | None = None
    sentiment_score: Decimal | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class CurrencyBias:
    currency: str
    score: Decimal
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PairBias:
    instrument: str
    base: CurrencyBias
    quote: CurrencyBias
    score: Decimal
    direction: str
    evidence: tuple[str, ...]
