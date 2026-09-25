"""Chat-agnostic Telegram delivery for Trade Oracle reports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

RequestSender = Callable[[Request], object]


class TelegramDeliveryError(RuntimeError):
    """Raised when Telegram rejects or cannot receive a message."""


@dataclass(frozen=True, slots=True)
class TelegramSender:
    """Send text to any Telegram chat addressed by its chat ID.

    The chat ID is deliberately supplied per call so the same adapter works
    for a private chat, group, or supergroup without changing Oracle logic.
    """

    bot_token: str
    request_sender: RequestSender = urlopen

    @classmethod
    def from_environment(cls) -> TelegramSender:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set")
        return cls(bot_token=token)

    def send_message(self, chat_id: str | int, text: str) -> None:
        """Send one plain-text message to the supplied Telegram chat."""
        if not text.strip():
            raise ValueError("Telegram message text cannot be empty")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            raw_response = self.request_sender(request)
        except (HTTPError, URLError) as exc:
            raise TelegramDeliveryError("Telegram request failed") from exc

        try:
            if hasattr(raw_response, "read"):
                raw_response = raw_response.read()
            response = json.loads(raw_response.decode("utf-8"))
        except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelegramDeliveryError("Telegram returned invalid JSON") from exc

        if response.get("ok") is not True:
            description = response.get("description", "Telegram rejected the message")
            raise TelegramDeliveryError(str(description))
