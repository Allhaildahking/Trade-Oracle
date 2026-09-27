"""Bounded in-memory storage for classified live market intelligence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.analysis.live_intelligence import classify_live_news
from app.models.fundamental import NewsItem
from app.models.live_intelligence import LiveIntelligence


@dataclass(slots=True)
class LiveIntelligenceBuffer:
    """Keep a recent, deduplicated snapshot for deterministic analysis."""

    max_items: int = 200
    max_age: timedelta = timedelta(hours=6)
    _items: dict[str, LiveIntelligence] = field(default_factory=dict)

    def add(self, item: NewsItem) -> LiveIntelligence:
        intelligence = classify_live_news(item)
        self._items[intelligence.news_id] = intelligence
        self._prune(intelligence.timestamp)
        return intelligence

    def snapshot(
        self,
        *,
        currencies: tuple[str, ...] = (),
        as_of: datetime | None = None,
    ) -> tuple[LiveIntelligence, ...]:
        now = as_of or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("as_of must be timezone-aware")

        self._prune(now)
        wanted = {currency.upper() for currency in currencies}
        items = (
            item
            for item in self._items.values()
            if not wanted or wanted.intersection(item.currencies)
        )
        return tuple(sorted(items, key=lambda item: item.timestamp))

    def _prune(self, now: datetime) -> None:
        cutoff = now - self.max_age
        self._items = {
            news_id: item
            for news_id, item in self._items.items()
            if item.timestamp >= cutoff
        }

        if len(self._items) <= self.max_items:
            return

        newest = sorted(
            self._items.items(),
            key=lambda pair: pair[1].timestamp,
            reverse=True,
        )
        self._items = dict(newest[: self.max_items])
