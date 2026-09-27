from datetime import UTC, datetime

from app.analysis.live_intelligence_feed import LiveIntelligenceFeed
from app.analysis.live_intelligence_buffer import LiveIntelligenceBuffer
from app.models.fundamental import NewsItem


def test_feed_routes_streamed_news_into_buffer() -> None:
    buffer = LiveIntelligenceBuffer()
    feed = LiveIntelligenceFeed(buffer)
    now = datetime(2026, 9, 27, 12, tzinfo=UTC)

    def stream(on_news):
        on_news(
            NewsItem(
                news_id="one",
                timestamp=now,
                title="Fed signals tighter policy",
                summary="",
                source_name="Reuters",
                url=None,
                currencies=("USD",),
                source="tree_news",
            )
        )

    feed.consume(stream)

    snapshot = buffer.snapshot(currencies=("USD",), as_of=now)
    assert [item.news_id for item in snapshot] == ["one"]
    assert snapshot[0].event_type == "CENTRAL_BANK"
