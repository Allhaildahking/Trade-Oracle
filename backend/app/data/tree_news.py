"""Real-time Tree News WebSocket adapter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
import json
import os
import re
from typing import Any

from app.data.http import ProviderError
from app.models.fundamental import NewsItem

TREE_NEWS_WS_URL = "wss://news.treeofalpha.com/ws"

_CURRENCY_PATTERNS = {
    "USD": re.compile(r"\b(?:usd|dollar|fed|fomc)\b", re.IGNORECASE),
    "EUR": re.compile(r"\b(?:eur|euro|ecb|lagarde)\b", re.IGNORECASE),
    "GBP": re.compile(r"\b(?:gbp|pound|boe|bank of england)\b", re.IGNORECASE),
    "JPY": re.compile(r"\b(?:jpy|yen|boj|bank of japan)\b", re.IGNORECASE),
    "CHF": re.compile(r"\b(?:chf|franc|snb|swiss)\b", re.IGNORECASE),
    "CAD": re.compile(r"\b(?:cad|canadian dollar|bank of canada)\b", re.IGNORECASE),
    "AUD": re.compile(r"\b(?:aud|australian dollar|rba|reserve bank of australia)\b", re.IGNORECASE),
    "NZD": re.compile(r"\b(?:nzd|new zealand dollar|rbnz|reserve bank of new zealand)\b", re.IGNORECASE),
}


def _timestamp(value: object) -> datetime:
    try:
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("Tree News payload has an invalid timestamp") from exc


def _currencies(text: str) -> tuple[str, ...]:
    return tuple(
        currency
        for currency, pattern in _CURRENCY_PATTERNS.items()
        if pattern.search(text)
    )


def parse_tree_news_message(payload: dict[str, Any]) -> NewsItem:
    title = str(payload.get("title") or "").strip()
    body = str(payload.get("body") or "").strip()
    if not title and not body:
        raise ValueError("Tree News payload has no headline")

    news_id = str(payload.get("_id") or payload.get("id") or "").strip()
    if not news_id:
        raise ValueError("Tree News payload has no news id")

    text = f"{title} {body}"
    return NewsItem(
        news_id=news_id,
        timestamp=_timestamp(payload.get("time")),
        title=title or body,
        summary=body,
        source_name=str(payload.get("source") or "").strip(),
        url=str(payload["link"]) if payload.get("link") else None,
        currencies=_currencies(text),
        sentiment_label=None,
        sentiment_score=None,
        source="tree_news",
    )


class TreeNewsStream:
    """Receive live Tree News headlines without coupling them to Telegram."""

    name = "tree_news"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        websocket_app_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("TREE_NEWS_API_KEY", "")
        if not self.api_key:
            raise ProviderError("TREE_NEWS_API_KEY is not configured.")
        self._websocket_app_factory = websocket_app_factory

    def stream(self, on_news: Callable[[NewsItem], None]) -> None:
        try:
            import websocket
        except ImportError as exc:
            raise ProviderError(
                "websocket-client is required for the Tree News stream."
            ) from exc

        factory = self._websocket_app_factory or websocket.WebSocketApp

        def on_open(ws: Any) -> None:
            ws.send(f"login {self.api_key}")

        def on_message(_ws: Any, message: str) -> None:
            try:
                payload = json.loads(message)
                if isinstance(payload, dict):
                    on_news(parse_tree_news_message(payload))
            except (json.JSONDecodeError, TypeError, ValueError):
                return

        app = factory(
            TREE_NEWS_WS_URL,
            on_open=on_open,
            on_message=on_message,
        )
        app.run_forever()
