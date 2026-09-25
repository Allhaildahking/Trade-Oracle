from datetime import UTC, datetime

from app.data import finance_calendar
from app.data.finance_calendar import FinanceCalendarProvider


def test_finance_calendar_maps_event_fields(monkeypatch):
    payload = {
        "events": [
            {
                "id": "fomc-1",
                "country": "United States",
                "currency": "USD",
                "title": "FOMC Rate Decision",
                "time_utc": "2026-09-24T18:00:00+00:00",
                "impact": "high",
                "actual": None,
                "consensus": "3.50",
                "prior": "3.75",
                "unit": "%",
            }
        ]
    }

    monkeypatch.setattr(finance_calendar, "get_json", lambda *_args, **_kwargs: payload)

    events = FinanceCalendarProvider().get_events(
        countries=("united states",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_id == "fomc-1"
    assert event.currency == "USD"
    assert event.title == "FOMC Rate Decision"
    assert event.importance == "high"
    assert event.forecast == 3.50
    assert event.previous == 3.75
    assert event.source == "financecalendar"


def test_finance_calendar_filters_requested_countries(monkeypatch):
    payload = {
        "events": [
            {
                "country": "United States",
                "currency": "USD",
                "title": "US CPI",
                "time_utc": "2026-09-24T12:00:00+00:00",
            },
            {
                "country": "Japan",
                "currency": "JPY",
                "title": "BOJ",
                "time_utc": "2026-09-24T13:00:00+00:00",
            },
        ]
    }
    monkeypatch.setattr(finance_calendar, "get_json", lambda *_args, **_kwargs: payload)

    events = FinanceCalendarProvider().get_events(
        countries=("japan",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert [event.currency for event in events] == ["JPY"]
