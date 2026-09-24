"""Evidence-based fundamental aggregation.

This is not a trade trigger. It converts macro evidence into a pair-relative
bias that the later decision engine can combine with technical structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.models.fundamental import EconomicEvent, NewsItem


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


def _event_signal(event: EconomicEvent) -> Decimal:
    if event.actual is None or event.forecast is None:
        return Decimal("0")
    if event.actual == event.forecast:
        return Decimal("0")
    direction = Decimal("1") if event.actual > event.forecast else Decimal("-1")
    importance = event.importance.lower()
    multiplier = Decimal("1.0")
    if "high" in importance:
        multiplier = Decimal("1.5")
    elif "low" in importance:
        multiplier = Decimal("0.5")
    return direction * multiplier


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
            evidence.append(f"{event.title}: actual vs forecast signal {signal:+}")

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
    evidence = base.evidence + quote.evidence
    return PairBias(instrument, base, quote, score, direction, evidence)
