"""Finance Calendar economic-calendar adapter."""

from datetime import UTC, datetime  # noqa: I001
from decimal import Decimal, InvalidOperation

from app.data.base import EconomicCalendarProvider
from app.data.http import ProviderError, get_json
from app.models.fundamental import EconomicEvent


_COUNTRY_CURRENCY = {
    "euro area": "EUR",
    "united kingdom": "GBP",
    "united states": "USD",
    "japan": "JPY",
    "switzerland": "CHF",
    "canada": "CAD",
    "australia": "AUD",
    "new zealand": "NZD",
}


def _decimal(value: object) -> Decimal | None:
    if value in (None, "", "null"):
        return None
    try:
        cleaned = str(value).replace(",", "").replace("%", "").strip()
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_datetime(value: object) -> datetime:
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _currency(row: dict[str, object], country: str) -> str:
    explicit = str(row.get("currency") or row.get("Currency") or "").upper()
    return explicit or _COUNTRY_CURRENCY.get(country.lower(), "")


def _country(row: dict[str, object]) -> str:
    return str(row.get("country") or row.get("Country") or "")


def _event_timestamp(row: dict[str, object]) -> datetime:
    value = row.get("time_utc") or row.get("timestamp") or row.get("date")
    if value is None:
        raise ValueError("missing event timestamp")
    return _parse_datetime(value)


class FinanceCalendarProvider(EconomicCalendarProvider):
    """Fetch scheduled economic events from Finance Calendar's free API."""

    name = "financecalendar"
    base_url = "https://www.financecalendar.com/wp-json/fc/v1"

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

        params: dict[str, str | int] = {
            "from": start_utc.strftime("%Y-%m-%d"),
            "to": end_utc.strftime("%Y-%m-%d"),
            "limit": 500,
        }
        payload = get_json(f"{self.base_url}/calendar", params)
        rows = payload.get("events", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ProviderError(f"Unexpected Finance Calendar response: {payload}")

        wanted = {country.lower() for country in countries}
        events: list[EconomicEvent] = []
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            country = _country(row)
            if wanted and country and country.lower() not in wanted:
                continue
            try:
                timestamp = _event_timestamp(row)
            except (TypeError, ValueError):
                continue
            if timestamp < start_utc or timestamp > end_utc:
                continue

            title = str(row.get("title") or row.get("name") or row.get("event") or "")
            event_key = str(
                row.get("id")
                or row.get("event_id")
                or row.get("url")
                or f"{timestamp.isoformat()}:{title}:{index}"
            )
            events.append(
                EconomicEvent(
                    event_id=event_key,
                    country=country,
                    currency=_currency(row, country),
                    title=title,
                    timestamp=timestamp,
                    importance=str(row.get("impact") or row.get("importance") or ""),
                    actual=_decimal(row.get("actual")),
                    forecast=_decimal(row.get("consensus") or row.get("forecast")),
                    previous=_decimal(row.get("prior") or row.get("previous")),
                    unit=str(row.get("unit")) if row.get("unit") else None,
                    source=self.name,
                )
            )

        return sorted(events, key=lambda event: event.timestamp)
