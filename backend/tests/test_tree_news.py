from datetime import UTC, datetime

from app.data.tree_news import parse_tree_news_message


def test_parse_tree_news_message_maps_live_headline() -> None:
    item = parse_tree_news_message(
        {
            "_id": "abc123",
            "title": "Reuters",
            "body": "Fed official signals possible rate cut as inflation cools.",
            "source": "Blogs",
            "time": 1779800000123,
            "link": "https://example.com/news",
        }
    )

    assert item.news_id == "abc123"
    assert item.title == "Reuters"
    assert item.summary.startswith("Fed official")
    assert item.source_name == "Blogs"
    assert item.url == "https://example.com/news"
    assert item.timestamp == datetime.fromtimestamp(1779800000.123, tz=UTC)
    assert item.source == "tree_news"


def test_parse_tree_news_message_detects_currency_mentions() -> None:
    item = parse_tree_news_message(
        {
            "_id": "xyz",
            "title": "Fed",
            "body": "USD and JPY markets react to the Bank of Japan statement.",
            "time": 1779800000123,
        }
    )

    assert item.currencies == ("USD", "JPY")


def test_parse_tree_news_message_rejects_non_news_payload() -> None:
    try:
        parse_tree_news_message({"ping": True})
    except ValueError as exc:
        assert "headline" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
