from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.runner import OracleRunner
from app.models.fundamental import EconomicEvent, NewsItem
from app.models.market import Candle, Quote


class FakeMarket:
    name = "fake-market"

    def __init__(self) -> None:
        self.timeframes: list[str] = []
        self.quotes: list[str] = []

    def get_candles(self, instrument, timeframe, *, start=None, end=None, limit=500):
        self.timeframes.append(timeframe)
        return [
            Candle(
                instrument=instrument,
                timeframe=timeframe,
                timestamp=datetime(2026, 9, 25, 8, tzinfo=UTC),
                open=Decimal("1.1000"),
                high=Decimal("1.1010"),
                low=Decimal("1.0990"),
                close=Decimal("1.1005"),
            )
        ]

    def get_quote(self, instrument):
        self.quotes.append(instrument)
        return Quote(
            instrument=instrument,
            timestamp=datetime(2026, 9, 25, 8, tzinfo=UTC),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1001"),
            mid=Decimal("1.10005"),
            source="fake",
        )


class FakeCalendar:
    name = "fake-calendar"

    def __init__(self) -> None:
        self.calls = []

    def get_events(self, *, countries, start=None, end=None):
        self.calls.append((countries, start, end))
        return [
            EconomicEvent(
                event_id="event-1",
                country="united states",
                currency="USD",
                title="GDP",
                timestamp=datetime(2026, 9, 25, 8, tzinfo=UTC),
                importance="LOW",
            )
        ]


class FakeNews:
    name = "fake-news"

    def __init__(self) -> None:
        self.calls = []

    def get_news(self, *, currencies=(), start=None, end=None, limit=50):
        self.calls.append((currencies, start, end, limit))
        return []


def test_runner_fetches_provider_evidence_and_analyzes() -> None:
    market = FakeMarket()
    calendar = FakeCalendar()
    news = FakeNews()
    runner = OracleRunner(market=market, calendar=calendar, news=news)

    result = runner.analyze_pair(
        "EURUSD",
        checked_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
    )

    assert result.instrument == "EURUSD"
    assert result.decision == "NO_TRADE"
    assert market.timeframes == ["4H", "1H", "15M", "5M"]
    assert market.quotes == ["EURUSD"]
    assert len(calendar.calls) == 2
    assert len(news.calls) == 1
