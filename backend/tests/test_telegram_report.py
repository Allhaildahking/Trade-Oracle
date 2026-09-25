from datetime import UTC, datetime

from app.delivery.telegram_report import TelegramReportPublisher
from app.models.oracle import OracleAnalysis

CHECKED_AT = datetime(2026, 9, 25, 8, tzinfo=UTC)


class FakeMarketRunner:
    def run_report(self, *, checked_at=None, rotation=None):
        assert checked_at == CHECKED_AT
        assert rotation is None
        return "TRADE ORACLE MARKET REPORT", (
            OracleAnalysis(
                instrument="EURUSD",
                decision="NO_TRADE",
                technical_score=0.5,
                weighted_score=0.5,
                setup=None,
                confirmation=None,
                trade=None,
                risk=None,
                reasons=("test",),
            ),
        )


class FakeTelegramSender:
    def __init__(self) -> None:
        self.messages: list[tuple[str | int, str]] = []

    def send_message(self, chat_id: str | int, text: str) -> None:
        self.messages.append((chat_id, text))


def test_publisher_delivers_the_same_rendered_report() -> None:
    sender = FakeTelegramSender()
    publisher = TelegramReportPublisher(
        market_runner=FakeMarketRunner(),
        sender=sender,
    )

    report, analyses = publisher.publish("-1001234567890", checked_at=CHECKED_AT)

    assert report == "TRADE ORACLE MARKET REPORT"
    assert len(analyses) == 1
    assert sender.messages == [
        ("-1001234567890", "TRADE ORACLE MARKET REPORT"),
    ]
