"""Rule-based live-market intelligence classification."""

from __future__ import annotations

import re

from app.models.fundamental import NewsItem
from app.models.live_intelligence import LiveEventType, LiveImpact, LiveIntelligence

_EVENT_RULES: tuple[tuple[LiveEventType, tuple[str, ...]], ...] = (
    (
        "CENTRAL_BANK",
        (
            "fed",
            "fomc",
            "ecb",
            "lagarde",
            "boe",
            "bank of england",
            "boj",
            "bank of japan",
            "snb",
            "bank of canada",
            "rba",
            "rbnz",
        ),
    ),
    (
        "TRADE_POLICY",
        ("tariff", "trade deal", "trade war", "export ban", "import ban", "sanction"),
    ),
    (
        "GEOPOLITICAL",
        ("war", "ceasefire", "missile", "invasion", "attack", "conflict", "military"),
    ),
    ("GOVERNMENT", ("government", "treasury", "finance ministry", "budget")),
    (
        "POLITICS",
        ("president", "prime minister", "election", "congress", "parliament"),
    ),
    (
        "MACRO",
        ("inflation", "cpi", "jobs", "employment", "gdp", "pmi", "retail sales"),
    ),
)

_POSITIVE_RULES = (
    "hawkish",
    "rate hike",
    "higher rates",
    "less easing",
    "tightening",
    "stronger growth",
)
_NEGATIVE_RULES = (
    "dovish",
    "rate cut",
    "lower rates",
    "more easing",
    "easing",
    "weaker growth",
)
_MIXED_RULES = ("uncertainty", "unclear", "mixed", "split", "volatile")

_CURRENCY_NAMES = {
    "USD": ("usd", "dollar", "fed", "fomc"),
    "EUR": ("eur", "euro", "ecb", "lagarde"),
    "GBP": ("gbp", "pound", "boe", "bank of england"),
    "JPY": ("jpy", "yen", "boj", "bank of japan"),
    "CHF": ("chf", "franc", "snb", "swiss"),
    "CAD": ("cad", "canadian dollar", "bank of canada"),
    "AUD": ("aud", "australian dollar", "rba"),
    "NZD": ("nzd", "new zealand dollar", "rbnz"),
}


def _matches(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(
        term
        for term in terms
        if re.search(
            r"(?<!\w)" + re.escape(term) + r"(?!\w)",
            lowered,
        )
    )


def _event_type(text: str) -> LiveEventType:
    for event_type, terms in _EVENT_RULES:
        if _matches(text, terms):
            return event_type
    return "OTHER"


def _currencies(item: NewsItem, text: str) -> tuple[str, ...]:
    detected = list(item.currencies)
    for currency, terms in _CURRENCY_NAMES.items():
        if _matches(text, terms) and currency not in detected:
            detected.append(currency)
    return tuple(detected)


def _impact(text: str) -> tuple[LiveImpact, tuple[str, ...]]:
    positive = _matches(text, _POSITIVE_RULES)
    negative = _matches(text, _NEGATIVE_RULES)
    mixed = _matches(text, _MIXED_RULES)
    evidence = tuple(f"impact keyword: {term}" for term in positive + negative + mixed)
    if positive and negative or mixed:
        return "MIXED", evidence
    if positive:
        return "POSITIVE", evidence
    if negative:
        return "NEGATIVE", evidence
    return "NEUTRAL", evidence


def classify_live_news(item: NewsItem) -> LiveIntelligence:
    """Interpret a live headline without turning it into a trading signal."""
    text = f"{item.title} {item.summary}".strip()
    event_type = _event_type(text)
    currencies = _currencies(item, text)
    impact, impact_evidence = _impact(text)

    evidence = tuple(
        [
            f"source: {item.source_name or 'unknown'}",
            f"event type: {event_type}",
            *(f"currency: {currency}" for currency in currencies),
            *impact_evidence,
        ]
    )
    confidence = min(
        1.0,
        0.35
        + (0.20 if item.source_name else 0.0)
        + (0.15 if currencies else 0.0)
        + (0.15 if event_type != "OTHER" else 0.0)
        + (0.15 if impact != "NEUTRAL" else 0.0),
    )
    implication = {
        "CENTRAL_BANK": "Potential change in monetary-policy expectations.",
        "TRADE_POLICY": "Potential change in trade conditions and currency expectations.",
        "GEOPOLITICAL": "Potential change in risk sentiment and safe-haven demand.",
        "GOVERNMENT": "Potential fiscal or policy impact.",
        "POLITICS": "Potential policy or political-risk impact.",
        "MACRO": "Potential change in economic or rate expectations.",
        "MARKET": "Potential direct market-impact information.",
        "OTHER": "No specific policy implication classified.",
    }[event_type]

    return LiveIntelligence(
        news_id=item.news_id,
        timestamp=item.timestamp,
        title=item.title,
        source_name=item.source_name,
        currencies=currencies,
        event_type=event_type,
        policy_implication=implication,
        market_impact=impact,
        confidence=confidence,
        evidence=evidence,
    )
