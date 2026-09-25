"""Initial fundamental evidence scoring.

This module deliberately stays conservative. Economic surprises are not all
directionally equivalent, so indicator semantics must be explicit. Unknown
events contribute zero directional score rather than being guessed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.data.base import EconomicCalendarProvider, NewsProvider
from app.models.fundamental import CurrencyBias, EconomicEvent, NewsItem, PairBias

INDICATOR_DIRECTION: dict[str, int] = {
    "inflation": 1,
    "cpi": 1,
    "ppi": 1,
    "interest rate": 1,
    "policy rate": 1,
    "fed funds": 1,
    "gdp": 1,
    "pmi": 1,
    "retail sales": 1,
    "wage": 1,
    "earnings": 1,
    "employment": 1,
    "unemployment": -1,
    "jobless claims": -1,
}


def _indicator_direction(title: str) -> int:
    lowered = title.lower()
    for keyword, direction in INDICATOR_DIRECTION.items():
        if keyword in lowered:
            return direction
    return 0


def _event_signal(event: EconomicEvent) -> Decimal:
    if event.actual is None or event.forecast is None or event.actual == event.forecast:
        return Decimal("0")
    direction = _indicator_direction(event.title)
    if direction == 0:
        return Decimal("0")
    surprise = Decimal("1") if event.actual > event.forecast else Decimal("-1")
    importance = event.importance.lower()
    multiplier = Decimal("1.0")
    if "high" in importance:
        multiplier = Decimal("1.5")
    elif "low" in importance:
        multiplier = Decimal("0.5")
    return surprise * direction * multiplier


def score_currency(
    currency: str,
    events: list[EconomicEvent],
    news: list[NewsItem],
) -> CurrencyBias:
    score = Decimal("0")
    evidence: list[str] = []

    for event in events:
        if event.currency.upper() != currency.upper():
            continue
        signal = _event_signal(event)
        if signal:
            score += signal
            evidence.append(f"{event.title}: surprise contribution {signal:+}")

    for item in news:
        if currency.upper() not in item.currencies or item.sentiment_score is None:
            continue
        score += item.sentiment_score
        evidence.append(f"News: {item.title} ({item.sentiment_label or 'unlabelled'})")

    score = max(Decimal("-10"), min(Decimal("10"), score))
    return CurrencyBias(currency.upper(), score, tuple(evidence[-10:]))


def score_pair(
    instrument: str,
    *,
    events: list[EconomicEvent],
    news: list[NewsItem],
    as_of: datetime | None = None,
) -> PairBias:
    if len(instrument) != 6 or not instrument.isalpha():
        raise ValueError("Pair must be a six-letter currency symbol.")
    if as_of is not None and as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if as_of is not None:
        events = [event for event in events if event.timestamp <= as_of]
        news = [item for item in news if item.timestamp <= as_of]
    base = score_currency(instrument[:3], events, news)
    quote = score_currency(instrument[3:], events, news)
    score = base.score - quote.score
    direction = "BUY" if score > 0 else "SELL" if score < 0 else "NEUTRAL"
    return PairBias(
        instrument, base, quote, score, direction, base.evidence + quote.evidence
    )


_CURRENCY_COUNTRIES = {
    "EUR": "euro area",
    "GBP": "united kingdom",
    "USD": "united states",
    "JPY": "japan",
    "CHF": "switzerland",
    "CAD": "canada",
    "AUD": "australia",
    "NZD": "new zealand",
}


def build_pair_bias(
    instrument: str,
    *,
    calendar: EconomicCalendarProvider,
    news: NewsProvider,
    as_of: datetime | None = None,
    lookback: timedelta = timedelta(days=7),
    lookahead: timedelta = timedelta(days=3),
) -> PairBias:
    """Fetch a reproducible point-in-time fundamental view for one pair."""
    if as_of is None:
        as_of = datetime.now(UTC)
    if as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if lookback < timedelta(0) or lookahead < timedelta(0):
        raise ValueError("lookback and lookahead must not be negative")
    if len(instrument) != 6 or not instrument.isalpha():
        raise ValueError("instrument must be a six-letter currency pair")

    pair = instrument.upper()
    currencies = (pair[:3], pair[3:])
    countries = tuple(
        _CURRENCY_COUNTRIES[currency]
        for currency in currencies
        if currency in _CURRENCY_COUNTRIES
    )
    events = calendar.get_events(
        countries=countries,
        start=as_of - lookback,
        end=as_of + lookahead,
    )
    news_items = news.get_news(
        currencies=currencies,
        start=as_of - lookback,
        end=as_of,
        limit=100,
    )
    return score_pair(pair, events=events, news=news_items, as_of=as_of)
