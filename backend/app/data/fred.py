"""FRED macroeconomic data adapter.

FRED is used for historical macro series. It is deliberately generic: the
Oracle can map a macro concept to a FRED series without coupling analysis to
FRED-specific response shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import os

from app.data.http import ProviderError, get_json


@dataclass(frozen=True, slots=True)
class MacroObservation:
    series_id: str
    date: datetime
    value: Decimal
    source: str = "fred"


class FREDProvider:
    name = "fred"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        if not self.api_key:
            raise ProviderError("FRED_API_KEY is not configured.")

    def get_observations(
        self,
        series_id: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[MacroObservation]:
        if not series_id.strip():
            raise ValueError("series_id is required.")

        params: dict[str, str | int] = {
            "api_key": self.api_key,
            "file_type": "json",
            "series_id": series_id,
            "sort_order": "desc",
            "limit": min(limit, 1000),
        }
        if start:
            params["observation_start"] = start.astimezone(UTC).date().isoformat()
        if end:
            params["observation_end"] = end.astimezone(UTC).date().isoformat()

        payload = get_json("https://api.stlouisfed.org/fred/series/observations", params)
        if not isinstance(payload, dict) or "observations" not in payload:
            raise ProviderError(f"Unexpected FRED response: {payload}")

        observations: list[MacroObservation] = []
        for row in payload.get("observations", []):
            if not isinstance(row, dict):
                continue
            raw_value = row.get("value")
            try:
                value = Decimal(str(raw_value))
                date = datetime.strptime(str(row["date"]), "%Y-%m-%d").replace(tzinfo=UTC)
            except (InvalidOperation, ValueError, TypeError, KeyError):
                continue
            observations.append(MacroObservation(series_id, date, value))

        return sorted(observations, key=lambda item: item.date, reverse=True)
