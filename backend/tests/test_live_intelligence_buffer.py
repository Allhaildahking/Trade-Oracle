from datetime import UTC, datetime, timedelta

from app.analysis.live_intelligence_buffer import LiveIntelligenceBuffer
from app.models.fundamental import NewsItem


def news(news_id: str, title: str, timestamp: datetime) -> NewsItem:
    return NewsItem(
        news_id=news_id,
        timestamp=timestamp,
        title=title,
        summary="",
        source_name="Reuters",
        url=None,
        currencies=("USD",),
        source="tree_news",
    )


def test_buffer_classifies_and_deduplicates_live_news() -> None:
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    buffer = LiveIntelligenceBuffer()

    first = buffer.add(news("one", "Fed announces rate hike", now))
    second = buffer.add(news("one", "Fed announces rate cut", now + timedelta(minutes=1)))

    snapshot = buffer.snapshot(currencies=("USD",), as_of=now + timedelta(minutes=1))

    assert first.news_id == "one"
    assert second.news_id == "one"
    assert len(snapshot) == 1
    assert snapshot[0].title == "Fed announces rate cut"


def test_buffer_filters_by_currency_and_age() -> None:
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)
    buffer = LiveIntelligenceBuffer(max_age=timedelta(hours=1))

    buffer.add(news("usd", "Fed signals tighter policy", now - timedelta(minutes=30)))
    buffer.add(
        NewsItem(
            news_id="eur",
            timestamp=now - timedelta(minutes=20),
            title="ECB signals tighter policy",
            summary="",
            source_name="Reuters",
            url=None,
            currencies=("EUR",),
            source="tree_news",
        )
    )
    buffer.add(news("old", "Fed statement", now - timedelta(hours=2)))

    usd = buffer.snapshot(currencies=("USD",), as_of=now)
    eur = buffer.snapshot(currencies=("EUR",), as_of=now)

    assert [item.news_id for item in usd] == ["usd"]
    assert [item.news_id for item in eur] == ["eur"]


def test_buffer_rejects_naive_snapshot_time() -> None:
    buffer = LiveIntelligenceBuffer()

    try:
        buffer.snapshot(as_of=datetime(2026, 9, 27, 12))
    except ValueError as exc:
        assert "timezone-aware" in str(exc)
    else:
        raise AssertionError("expected ValueError")
