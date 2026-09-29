"""Provider-backed orchestration for live Trade Oracle analysis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.analysis.fundamentals import build_pair_bias
from app.analysis.oracle import analyze_pair
from app.core.constants import TIMEFRAMES
from app.data.base import EconomicCalendarProvider, MarketDataProvider, NewsProvider
from app.data.live_snapshot import InstrumentSnapshot, LiveMarketSnapshot
from app.models.fundamental import EconomicEvent
from app.models.oracle import OracleAnalysis


@dataclass(frozen=True, slots=True)
class OracleRunner:
    """Fetch current evidence from providers and run the deterministic Oracle."""

    market: MarketDataProvider
    calendar: EconomicCalendarProvider
    news: NewsProvider

    def analyze_pair(
        self,
        instrument: str,
        *,
        checked_at: datetime | None = None,
        duplicate_active: bool = False,
        snapshot: LiveMarketSnapshot | None = None,
    ) -> OracleAnalysis:
        now = checked_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")

        if snapshot is not None:
            if snapshot.checked_at != now:
                raise ValueError("snapshot checked_at must match analysis checked_at")
            try:
                evidence = snapshot.markets[instrument]
            except KeyError as exc:
                raise ValueError(f"snapshot missing instrument: {instrument}") from exc
            candles = evidence.candles
            quote = evidence.quote
            pair_bias = self._pair_bias_from_snapshot(
                instrument, evidence, now
            )
            stale_reasons = _snapshot_staleness_reasons(evidence, now)
            if stale_reasons:
                return OracleAnalysis(
                    instrument=instrument,
                    decision="BLOCKED",
                    technical_score=0.0,
                    weighted_score=0.0,
                    setup=None,
                    confirmation=None,
                    trade=None,
                    risk=None,
                    reasons=tuple(stale_reasons),
                )
            events = tuple(
                event for event in evidence.events if event.timestamp <= now
            )
        else:
            candles = {
                timeframe: self.market.get_candles(instrument, timeframe, limit=500)
                for timeframe in TIMEFRAMES
            }
            quote = self.market.get_quote(instrument)
            pair_bias = build_pair_bias(
                instrument,
                calendar=self.calendar,
                news=self.news,
                as_of=now,
            )
            events = self._economic_events(instrument, now)

        return analyze_pair(
            candles_4h=candles["4H"],
            candles_1h=candles["1H"],
            candles_15m=candles["15M"],
            candles_5m=candles["5M"],
            pair_bias=pair_bias,
            quote=quote,
            economic_events=events,
            checked_at=now,
            duplicate_active=duplicate_active,
        )

    def _pair_bias_from_snapshot(
        self,
        instrument: str,
        evidence: InstrumentSnapshot,
        checked_at: datetime,
    ):
        from app.analysis.fundamentals import score_pair

        return score_pair(
            instrument,
            events=list(evidence.events),
            news=list(evidence.news),
            as_of=checked_at,
        )

    def _economic_events(
        self,
        instrument: str,
        checked_at: datetime,
    ) -> tuple[EconomicEvent, ...]:
        currencies = _instrument_currencies(instrument)
        countries = tuple(
            _CURRENCY_COUNTRIES[currency]
            for currency in currencies
            if currency in _CURRENCY_COUNTRIES
        )
        if not countries:
            return ()
        events = self.calendar.get_events(
            countries=countries,
            start=checked_at - timedelta(minutes=30),
            end=checked_at + timedelta(minutes=30),
        )
        return tuple(events)


_MAX_CANDLE_AGE = {
    "4H": timedelta(hours=6),
    "1H": timedelta(hours=2),
    "15M": timedelta(minutes=30),
    "5M": timedelta(minutes=10),
}
_MAX_QUOTE_AGE = timedelta(minutes=2)


def _snapshot_staleness_reasons(
    evidence: InstrumentSnapshot,
    checked_at: datetime,
) -> tuple[str, ...]:
    reasons: list[str] = []
    for timeframe, max_age in _MAX_CANDLE_AGE.items():
        candles = evidence.candles.get(timeframe)
        if not candles:
            reasons.append(f"BLOCKED: missing {timeframe} market data")
            continue
        latest = max(candles, key=lambda candle: candle.timestamp)
        age = checked_at - latest.timestamp
        if age > max_age:
            reasons.append(
                f"BLOCKED: stale {timeframe} data ({int(age.total_seconds() // 60)}m old)"
            )
    quote_age = checked_at - evidence.quote.timestamp
    if quote_age > _MAX_QUOTE_AGE:
        reasons.append(
            f"BLOCKED: stale quote ({int(quote_age.total_seconds() // 60)}m old)"
        )
    return tuple(reasons)


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


def _instrument_currencies(instrument: str) -> tuple[str, ...]:
    pair = instrument.upper()
    if len(pair) != 6:
        raise ValueError("instrument must be a six-letter symbol")
    return pair[:3], pair[3:]
