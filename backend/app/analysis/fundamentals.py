"""Initial fundamental evidence scoring.

This module deliberately stays conservative. Economic surprises are not all
directionally equivalent, so indicator semantics must be explicit. Unknown
events contribute zero directional score rather than being guessed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.analysis.live_intelligence import score_live_intelligence
from app.data.base import EconomicCalendarProvider, NewsProvider
from app.models.fundamental import CurrencyBias, EconomicEvent, NewsItem, PairBias
from app.models.live_intelligence import LiveIntelligence

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
    live_intelligence: tuple[LiveIntelligence, ...] = (),
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

    for intelligence in live_intelligence:
        contribution = score_live_intelligence(intelligence, currency)
        if contribution:
            score += contribution
            evidence.append(
                f"Live: {intelligence.title} ({intelligence.market_impact}, "
                f"confidence={intelligence.confidence:.2f})"
            )

    score = max(Decimal("-10"), min(Decimal("10"), score))
    return CurrencyBias(currency.upper(), score, tuple(evidence[-10:]))


_GOLD_DRIVER_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    ("real_yields_falling", 1, ("real yields fall", "real yields decline", "real yields drop", "real rates fall", "real rates decline")),
    ("real_yields_rising", -1, ("real yields rise", "real yields climb", "real yields jump", "real rates rise", "real rates climb")),
    ("fed_dovish", 1, ("fed signals rate cuts", "fed rate cut", "fed turns dovish", "dovish fed", "monetary easing")),
    ("fed_hawkish", -1, ("fed signals rate hikes", "fed rate hike", "fed turns hawkish", "hawkish fed", "monetary tightening")),
    ("usd_weakness", 1, ("dollar weakens", "dollar falls", "usd weakens", "dollar slides")),
    ("usd_strength", -1, ("dollar strengthens", "dollar rises", "usd strengthens", "dollar rallies")),
    ("central_bank_buying", 1, ("central bank gold buying", "central banks buy gold", "central bank purchases gold", "gold reserves increase")),
    ("central_bank_selling", -1, ("central bank gold selling", "central banks sell gold", "central bank sells gold")),
    ("gold_etf_inflows", 1, ("gold etf inflows", "gold etf sees inflows", "gold etf holdings rise")),
    ("gold_etf_outflows", -1, ("gold etf outflows", "gold etf sees outflows", "gold etf holdings fall")),
    ("geopolitical_escalation", 1, ("geopolitical tensions escalate", "war escalates", "military escalation", "safe haven demand rises")),
    ("geopolitical_relief", -1, ("geopolitical tensions ease", "ceasefire agreed", "peace deal reached", "safe haven demand fades")),
)


def _gold_news_signal(item: NewsItem) -> tuple[Decimal, tuple[str, ...]]:
    """Score only explicit, directional gold drivers; ambiguous headlines score zero."""
    text = f"{item.title} {item.summary}".lower()
    matches = [
        (name, direction)
        for name, direction, phrases in _GOLD_DRIVER_RULES
        if any(phrase in text for phrase in phrases)
    ]
    directions = {direction for _, direction in matches}
    if len(directions) != 1:
        return Decimal("0"), ()
    # One headline contributes at most one point, even if it repeats a driver.
    direction = next(iter(directions))
    names = ", ".join(name for name, _ in matches)
    return Decimal(direction), (f"Gold driver: {names} ({item.title})",)


def _score_gold_news(news: list[NewsItem]) -> CurrencyBias:
    score = Decimal("0")
    evidence: list[str] = []
    for item in news:
        signal, details = _gold_news_signal(item)
        if signal:
            score += signal
            evidence.extend(details)
    score = max(Decimal("-10"), min(Decimal("10"), score))
    return CurrencyBias("XAU", score, tuple(evidence[-10:]))


def score_pair(
    instrument: str,
    *,
    events: list[EconomicEvent],
    news: list[NewsItem],
    live_intelligence: tuple[LiveIntelligence, ...] = (),
    as_of: datetime | None = None,
) -> PairBias:
    currencies = _instrument_currencies(instrument)
    if as_of is not None and as_of.tzinfo is None:
        raise ValueError("as_of must be timezone-aware")
    if as_of is not None:
        events = [event for event in events if event.timestamp <= as_of]
        news = [item for item in news if item.timestamp <= as_of]
        live_intelligence = tuple(
            item for item in live_intelligence if item.timestamp <= as_of
        )
    if currencies[0] == "XAU":
        base = _score_gold_news(news)
    else:
        base = score_currency(currencies[0], events, news, live_intelligence)
    quote = score_currency(currencies[1], events, news, live_intelligence)
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


def fundamental_strength(pair_bias: PairBias) -> float:
    """Normalize directional fundamental conviction to the decision layer's 0-1 scale."""
    if pair_bias.direction == "NEUTRAL":
        return 0.0
    return float(min(Decimal("1"), abs(pair_bias.score) / Decimal("10")))


def build_pair_bias(
    instrument: str,
    *,
    calendar: EconomicCalendarProvider,
    news: NewsProvider,
    live_intelligence: tuple[LiveIntelligence, ...] = (),
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
    currencies = _instrument_currencies(instrument)
    pair = instrument.upper()
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
    return score_pair(
        pair,
        events=events,
        news=news_items,
        live_intelligence=live_intelligence,
        as_of=as_of,
    )



def _instrument_currencies(instrument: str) -> tuple[str, str]:
    """Resolve broker symbols to their underlying fundamental currencies."""
    symbol = instrument.upper()
    if symbol.startswith("XAUUSD"):
        return "XAU", "USD"
    if len(symbol) == 6 and symbol.isalpha():
        return symbol[:3], symbol[3:]
    raise ValueError("instrument must be a supported six-letter pair or XAUUSD broker symbol")
