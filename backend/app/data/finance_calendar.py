"""Free public economic-calendar adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.data.base import EconomicCalendarProvider
from app.data.http import ProviderError, get_json
from app.models.fundamental import EconomicEvent

_CURRENCY_COUNTRY = {
    "AUD": "australia",
    "CAD": "canada",
    "CHF": "switzerland",
    "EUR": "euro area",
    "GBP": "united kingdom",
    "JPY": "japan",
    "NZD": "new zealand",
    "USD": "united states",
}

_COUNTRY_CURRENCY = {value: key for key, value in _CURRENCY_COUNTRY.items()}
_FEEDS = (
    "https://nfs.faireconomy.media/ff_calendar_prevweek.json",
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
)


def _parse_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _parse_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    try:
        return Decimal(text)
    except (ArithmeticError, ValueError):
        return None


class FinanceCalendarProvider(EconomicCalendarProvider):
    """Fetch scheduled macro releases from a public calendar JSON feed."""

    name = "fair_economy"

    def get_events(
        self,
        *,
        countries: tuple[str, ...],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[EconomicEvent]:
        if start is not None and start.tzinfo is None:
            raise ValueError("start must be timezone-aware")
        if end is not None and end.tzinfo is None:
            raise ValueError("end must be timezone-aware")

        start_utc = (start or datetime.now(UTC)).astimezone(UTC)
        end_utc = (end or start_utc).astimezone(UTC)
        if end_utc < start_utc:
            raise ValueError("end must not be before start")

        requested = {
            _COUNTRY_CURRENCY[country.lower()]
            for country in countries
            if country.lower() in _COUNTRY_CURRENCY
        }
        if not requested:
            return []

        events: list[EconomicEvent] = []
        seen: set[tuple[str, datetime, str]] = set()

        for feed_url in _FEEDS:
            payload = get_json(feed_url)
            if not isinstance(payload, list):
                raise ProviderError(
                    f"Unexpected economic-calendar response: {payload}"
                )

            for row in payload:
                if not isinstance(row, dict):
                    continue

                currency = str(row.get("country", "")).upper()
                if currency not in requested:
                    continue

                try:
                    timestamp = _parse_datetime(row["date"])
                except (KeyError, TypeError, ValueError):
                    continue

                if timestamp < start_utc or timestamp > end_utc:
                    continue

                title = str(row.get("title") or "Economic release")
                event_key = (currency, timestamp, title)
                if event_key in seen:
                    continue
                seen.add(event_key)

                events.append(
                    EconomicEvent(
                        event_id=f"{currency}:{timestamp.isoformat()}:{title}",
                        country=_CURRENCY_COUNTRY[currency],
                        currency=currency,
                        title=title,
                        timestamp=timestamp,
                        importance=str(row.get("impact") or ""),
                        forecast=_parse_decimal(row.get("forecast")),
                        previous=_parse_decimal(row.get("previous")),
                        source=self.name,
                    )
                )

        return sorted(events, key=lambda event: event.timestamp)
