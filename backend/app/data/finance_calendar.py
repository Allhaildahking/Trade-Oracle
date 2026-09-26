"""Local economic-calendar feed adapter."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path

from app.data.base import EconomicCalendarProvider
from app.data.http import ProviderError
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
_DEFAULT_FEED_PATH = Path(__file__).resolve().parents[3] / "calendar" / "calendar.json"


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
    """Read scheduled macro releases from the committed calendar feed."""

    name = "forex_factory_feed"

    def __init__(self, feed_path: Path | str = _DEFAULT_FEED_PATH) -> None:
        self.feed_path = Path(feed_path)

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

        try:
            rows = json.loads(self.feed_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProviderError(
                f"Economic calendar feed not found: {self.feed_path}"
            ) from exc
        except json.JSONDecodeError as exc:
            raise ProviderError(
                f"Economic calendar feed is invalid JSON: {self.feed_path}"
            ) from exc

        if not isinstance(rows, list):
            raise ProviderError("Economic calendar feed must contain a JSON list")

        events: list[EconomicEvent] = []
        seen: set[tuple[str, datetime, str]] = set()

        for row in rows:
            if not isinstance(row, dict):
                continue

            currency = str(row.get("currency") or "").upper()
            if currency not in requested:
                continue

            try:
                timestamp = _parse_datetime(row["datetime_utc"])
            except (KeyError, TypeError, ValueError):
                continue

            if timestamp < start_utc or timestamp > end_utc:
                continue

            title = str(row.get("event") or "Economic release")
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
                    actual=_parse_decimal(row.get("actual")),
                    forecast=_parse_decimal(row.get("forecast")),
                    previous=_parse_decimal(row.get("previous")),
                    source=self.name,
                )
            )

        return sorted(events, key=lambda event: event.timestamp)
