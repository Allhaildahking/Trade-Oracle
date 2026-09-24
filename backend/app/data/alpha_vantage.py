"""Alpha Vantage news/sentiment adapter.

Used primarily for market-news context. It is intentionally separate from the
price provider so Trade Oracle can swap market-data vendors independently.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import os

from app.data.base import NewsProvider
from app.data.http import ProviderError, get_json
from app.models.fundamental import NewsItem


def _decimal(value: object) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_timestamp(value: object) -> datetime:
    text = str(value)
    parsed = datetime.strptime(text, "%Y%m%dT%H%M%S")
    return parsed.replace(tzinfo=UTC)


class AlphaVantageNewsProvider(NewsProvider):
    name = "alpha_vantage"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY", "")
        if not self.api_key:
            raise ProviderError("ALPHA_VANTAGE_API_KEY is not configured.")

    def get_news(
        self,
        *,
        currencies: tuple[str, ...] = (),
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsItem]:
        params: dict[str, str | int] = {
            "function": "NEWS_SENTIMENT",
            "limit": min(limit, 1000),
            "sort": "LATEST",
            "apikey": self.api_key,
        }
        if currencies:
            params["topics"] = ",".join(f"forex:{currency.lower()}" for currency in currencies)
        if start:
            params["time_from"] = start.astimezone(UTC).strftime("%Y%m%dT%H%M")
        if end:
            params["time_to"] = end.astimezone(UTC).strftime("%Y%m%dT%H%M")

        payload = get_json("https://www.alphavantage.co/query", params)
        if not isinstance(payload, dict) or "feed" not in payload:
            raise ProviderError(f"Unexpected Alpha Vantage response: {payload}")

        items: list[NewsItem] = []
        for row in payload.get("feed", []):
            if not isinstance(row, dict):
                continue
            currencies_seen: set[str] = set()
            for topic in row.get("topics", []):
                if isinstance(topic, dict) and str(topic.get("topic", "")).startswith("forex:"):
                    currencies_seen.add(str(topic["topic"]).split(":", 1)[1].upper())
            items.append(
                NewsItem(
                    news_id=str(row.get("url") or row.get("title")),
                    timestamp=_parse_timestamp(row.get("time_published")),
                    title=str(row.get("title", "")),
                    summary=str(row.get("summary", "")),
                    source_name=str(row.get("source", "")),
                    url=str(row["url"]) if row.get("url") else None,
                    currencies=tuple(sorted(currencies_seen)),
                    sentiment_label=str(row["overall_sentiment_label"])
                    if row.get("overall_sentiment_label")
                    else None,
                    sentiment_score=_decimal(row.get("overall_sentiment_score")),
                    source=self.name,
                )
            )
        return sorted(items, key=lambda item: item.timestamp, reverse=True)
