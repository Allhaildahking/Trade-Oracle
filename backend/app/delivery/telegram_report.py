"""Telegram delivery orchestration for completed Trade Oracle reports."""

from __future__ import annotations

from dataclasses import dataclass

from app.analysis.market_runner import MarketRunner
from app.delivery.telegram import TelegramSender
from app.models.oracle import OracleAnalysis


@dataclass(frozen=True, slots=True)
class TelegramReportPublisher:
    """Run a market report and deliver it to one Telegram chat."""

    market_runner: MarketRunner
    sender: TelegramSender

    def publish(
        self,
        chat_id: str | int,
        *,
        checked_at=None,
        rotation=None,
    ) -> tuple[str, tuple[OracleAnalysis, ...]]:
        """Render the current market report and send it to the target chat."""
        report, analyses = self.market_runner.run_report(
            checked_at=checked_at,
            rotation=rotation,
        )
        self.sender.send_message(chat_id, report)
        return report, analyses
