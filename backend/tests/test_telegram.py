import json
from urllib.request import Request

import pytest

from app.delivery.telegram import TelegramDeliveryError, TelegramSender


class FakeTelegramResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __call__(self, request: Request) -> bytes:
        assert request.full_url == "https://api.telegram.org/botTEST_TOKEN/sendMessage"
        assert request.method == "POST"
        assert request.get_header("Content-type") == "application/json"
        assert json.loads(request.data.decode("utf-8")) == {
            "chat_id": "-1001234567890",
            "text": "TRADE ORACLE MARKET REPORT",
        }
        return json.dumps(self.payload).encode("utf-8")


def test_telegram_sender_targets_chat_id_without_knowing_chat_type() -> None:
    sender = TelegramSender(
        bot_token="TEST_TOKEN",
        request_sender=FakeTelegramResponse({"ok": True, "result": {"message_id": 1}}),
    )

    sender.send_message("-1001234567890", "TRADE ORACLE MARKET REPORT")


def test_telegram_sender_rejects_empty_messages() -> None:
    sender = TelegramSender(bot_token="TEST_TOKEN", request_sender=lambda _: b'{"ok":true}')

    with pytest.raises(ValueError, match="cannot be empty"):
        sender.send_message("123", "   ")


def test_telegram_sender_surfaces_telegram_rejection() -> None:
    sender = TelegramSender(
        bot_token="TEST_TOKEN",
        request_sender=FakeTelegramResponse(
            {"ok": False, "description": "chat not found"},
        ),
    )

    with pytest.raises(TelegramDeliveryError, match="chat not found"):
        sender.send_message("123", "hello")
