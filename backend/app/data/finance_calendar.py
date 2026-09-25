"""FXMacroData economic-calendar adapter."""

from datetime import UTC, datetime  # noqa: I001

from app.data.base import EconomicCalendarProvider
from app.data.http import ProviderError, get_json
from app.models.fundamental import EconomicEvent


_COUNTRY_CURRENCY = {
    "euro area": "eur",
    "united kingdom": "gbp",
    "united states": "usd",
    "japan": "jpy",
    "switzerland": "chf",
    "canada": "cad",
    "australia": "aud",
    "new zealand": "nzd",
}


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


def _event_timestamp(row: dict[str, object]) -> datetime:
    for key in ("announcement_datetime", "release_datetime", "timestamp", "date"):
        value = row.get(key)
        if value is not None:
            return _parse_datetime(value)
    raise ValueError("missing event timestamp")


class FinanceCalendarProvider(EconomicCalendarProvider):
    """Fetch scheduled macro releases from FXMacroData's public calendar API."""

    name = "fxmacrodata"
    base_url = "https://api.fxmacrodata.com/v1/calendar"

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

        currencies = tuple(
            _COUNTRY_CURRENCY[country.lower()]
            for country in countries
            if country.lower() in _COUNTRY_CURRENCY
        )

        events: list[EconomicEvent] = []
        for currency in currencies:
            payload = get_json(f"{self.base_url}/{currency}")
            rows = payload.get("data", []) if isinstance(payload, dict) else payload
            if not isinstance(rows, list):
                raise ProviderError(
                    f"Unexpected FXMacroData response for {currency}: {payload}"
                )

            for index, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
                try:
                    timestamp = _event_timestamp(row)
                except (TypeError, ValueError):
                    continue
                if timestamp < start_utc or timestamp > end_utc:
                    continue

                indicator = str(
                    row.get("indicator")
                    or row.get("title")
                    or row.get("name")
                    or "Economic release"
                )
                event_id = str(
                    row.get("event_id")
                    or row.get("id")
                    or f"{currency}:{timestamp.isoformat()}:{indicator}:{index}"
                )
                importance = str(
                    row.get("importance")
                    or row.get("impact")
                    or ""
                )
                events.append(
                    EconomicEvent(
                        event_id=event_id,
                        country=next(
                            (
                                country
                                for country, code in _COUNTRY_CURRENCY.items()
                                if code == currency
                            ),
                            "",
                        ),
                        currency=currency.upper(),
                        title=indicator,
                        timestamp=timestamp,
                        importance=importance,
                        source=self.name,
                    )
                )

        return sorted(events, key=lambda event: event.timestamp)
