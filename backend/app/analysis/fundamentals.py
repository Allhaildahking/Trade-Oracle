"""Initial fundamental evidence scoring.

This module deliberately stays conservative. Economic surprises are not all
directionally equivalent, so indicator semantics must be explicit. Unknown
events contribute zero directional score rather than being guessed.
"""

from __future__ import annotations

from decimal import Decimal

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
) -> PairBias:
    if len(instrument) != 6 or not instrument.isalpha():
        raise ValueError("Pair must be a six-letter currency symbol.")
    base = score_currency(instrument[:3], events, news)
    quote = score_currency(instrument[3:], events, news)
    score = base.score - quote.score
    direction = "BUY" if score > 0 else "SELL" if score < 0 else "NEUTRAL"
    return PairBias(
        instrument, base, quote, score, direction, base.evidence + quote.evidence
    )
