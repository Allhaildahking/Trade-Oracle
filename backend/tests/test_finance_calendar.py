from datetime import UTC, datetime
from decimal import Decimal
import json

import pytest

from app.data.finance_calendar import FinanceCalendarProvider


def _write_feed(tmp_path, rows):
    path = tmp_path / "calendar.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return path


def test_finance_calendar_maps_event_fields(tmp_path):
    feed = _write_feed(
        tmp_path,
        [
            {
                "event": "FOMC Rate Decision",
                "currency": "USD",
                "datetime_utc": "2026-09-24T14:00:00Z",
                "impact": "red",
                "actual": "4.25%",
                "forecast": "4.25%",
                "previous": "4.50%",
            }
        ],
    )

    events = FinanceCalendarProvider(feed).get_events(
        countries=("united states",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert len(events) == 1
    event = events[0]
    assert event.currency == "USD"
    assert event.country == "united states"
    assert event.title == "FOMC Rate Decision"
    assert event.importance == "red"
    assert event.actual == Decimal("4.25")
    assert event.forecast == Decimal("4.25")
    assert event.previous == Decimal("4.50")
    assert event.source == "forex_factory_feed"


def test_finance_calendar_filters_requested_countries(tmp_path):
    feed = _write_feed(
        tmp_path,
        [
            {
                "event": "USD release",
                "currency": "USD",
                "datetime_utc": "2026-09-24T12:00:00Z",
                "impact": "yellow",
            },
            {
                "event": "JPY release",
                "currency": "JPY",
                "datetime_utc": "2026-09-24T12:30:00Z",
                "impact": "red",
            },
        ],
    )

    events = FinanceCalendarProvider(feed).get_events(
        countries=("japan",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert [event.currency for event in events] == ["JPY"]


def test_finance_calendar_deduplicates_rows(tmp_path):
    row = {
        "event": "CPI",
        "currency": "USD",
        "datetime_utc": "2026-09-24T12:30:00Z",
        "impact": "red",
    }
    events = FinanceCalendarProvider(_write_feed(tmp_path, [row, row])).get_events(
        countries=("united states",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert len(events) == 1


def test_finance_calendar_missing_feed_raises(tmp_path):
    with pytest.raises(Exception, match="feed not found"):
        FinanceCalendarProvider(tmp_path / "missing.json").get_events(
            countries=("united states",),
            start=datetime(2026, 9, 24, 0, tzinfo=UTC),
            end=datetime(2026, 9, 25, 0, tzinfo=UTC),
        )
