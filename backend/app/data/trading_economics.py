"""Trading Economics economic-calendar adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import os

from app.data.base import EconomicCalendarProvider
from app.data.http import ProviderError, get_json
from app.models.fundamental import EconomicEvent


def _decimal(value: object) -> Decimal | None:
    if value in (None, "", "null"):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _parse_datetime(value: object) -> datetime:
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC)


class TradingEconomicsProvider(EconomicCalendarProvider):
    name = "trading_economics"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("TRADING_ECONOMICS_API_KEY", "")
        if not self.api_key:
            raise ProviderError("TRADING_ECONOMICS_API_KEY is not configured.")

    def get_events(
        self,
        *,
        countries: tuple[str, ...],
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[EconomicEvent]:
        country_path = ",".join(countries)
        params: dict[str, str | int] = {"c": self.api_key}
        if start:
            params["d1"] = start.astimezone(UTC).strftime("%Y-%m-%d")
        if end:
            params["d2"] = end.astimezone(UTC).strftime("%Y-%m-%d")

        payload = get_json(
            f"https://api.tradingeconomics.com/calendar/country/{country_path}",
            params,
        )
        if not isinstance(payload, list):
            raise ProviderError(f"Unexpected Trading Economics response: {payload}")

        events: list[EconomicEvent] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            events.append(
                EconomicEvent(
                    event_id=str(row.get("CalendarId") or row.get("ID") or row.get("Ticker")),
                    country=str(row.get("Country", "")),
                    currency=str(row.get("Currency", "")),
                    title=str(row.get("Event") or row.get("Category", "")),
                    timestamp=_parse_datetime(row.get("Date")),
                    importance=str(row.get("Importance", "")),
                    actual=_decimal(row.get("Actual")),
                    forecast=_decimal(row.get("Forecast")),
                    previous=_decimal(row.get("Previous")),
                    unit=str(row.get("Unit")) if row.get("Unit") else None,
                    source=self.name,
                )
            )
        return sorted(events, key=lambda event: event.timestamp)
