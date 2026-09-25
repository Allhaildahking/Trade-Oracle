from datetime import UTC, datetime
from decimal import Decimal

from app.data import finance_calendar
from app.data.finance_calendar import FinanceCalendarProvider


def test_finance_calendar_maps_event_fields(monkeypatch):
    payload = [
        {
            "title": "FOMC Rate Decision",
            "country": "USD",
            "date": "2026-09-24T14:00:00+00:00",
            "impact": "High",
            "forecast": "4.25%",
            "previous": "4.50%",
        }
    ]

    monkeypatch.setattr(
        finance_calendar,
        "get_json",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(finance_calendar, "_FEEDS", ("feed",))

    events = FinanceCalendarProvider().get_events(
        countries=("united states",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert len(events) == 1
    event = events[0]
    assert event.currency == "USD"
    assert event.country == "united states"
    assert event.title == "FOMC Rate Decision"
    assert event.importance == "High"
    assert event.forecast == Decimal("4.25")
    assert event.previous == Decimal("4.50")
    assert event.actual is None
    assert event.source == "fair_economy"


def test_finance_calendar_filters_requested_countries(monkeypatch):
    def fake_get_json(*_args, **_kwargs):
        return [
            {
                "title": "USD release",
                "country": "USD",
                "date": "2026-09-24T12:00:00+00:00",
                "impact": "Low",
            },
            {
                "title": "JPY release",
                "country": "JPY",
                "date": "2026-09-24T12:30:00+00:00",
                "impact": "High",
            },
        ]

    monkeypatch.setattr(finance_calendar, "get_json", fake_get_json)
    monkeypatch.setattr(finance_calendar, "_FEEDS", ("feed",))

    events = FinanceCalendarProvider().get_events(
        countries=("japan",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert [event.currency for event in events] == ["JPY"]


def test_finance_calendar_deduplicates_overlapping_feeds(monkeypatch):
    payload = [
        {
            "title": "CPI",
            "country": "USD",
            "date": "2026-09-24T12:30:00+00:00",
            "impact": "High",
        }
    ]

    monkeypatch.setattr(
        finance_calendar,
        "get_json",
        lambda *_args, **_kwargs: payload,
    )
    monkeypatch.setattr(
        finance_calendar,
        "_FEEDS",
        ("previous", "this", "next"),
    )

    events = FinanceCalendarProvider().get_events(
        countries=("united states",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert len(events) == 1
