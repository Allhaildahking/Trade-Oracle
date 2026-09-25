from datetime import UTC, datetime

from app.data import finance_calendar
from app.data.finance_calendar import FinanceCalendarProvider


def test_finance_calendar_maps_event_fields(monkeypatch):
    payload = {
        "data": [
            {
                "event_id": "fomc-1",
                "indicator": "FOMC Rate Decision",
                "announcement_datetime": 1790272800,
                "importance": "high",
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
    assert event.source == "fxmacrodata"


def test_finance_calendar_filters_requested_countries(monkeypatch):
    def fake_get_json(url, *_args, **_kwargs):
        currency = url.rsplit("/", 1)[-1]
        return {
            "data": [
                {
                    "indicator": f"{currency.upper()} release",
                    "announcement_datetime": 1790251200,
                }
            ]
        }

    monkeypatch.setattr(finance_calendar, "get_json", fake_get_json)

    events = FinanceCalendarProvider().get_events(
        countries=("japan",),
        start=datetime(2026, 9, 24, 0, tzinfo=UTC),
        end=datetime(2026, 9, 25, 0, tzinfo=UTC),
    )

    assert [event.currency for event in events] == ["JPY"]
