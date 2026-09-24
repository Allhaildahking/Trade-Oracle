"""LLM reasoning adapter for Trade Oracle.

The deterministic Oracle engine owns decisions and risk rules. This client is
for interpretation, summaries, and explanations after structured evidence has
been calculated.
"""

from __future__ import annotations

import os
from typing import Any

from app.data.http import ProviderError, get_json


class GroqReasoner:
    name = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = "openai/gpt-oss-120b",
    ) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not configured.")
        self.model = model

    def complete(self, *, system: str, user: str, temperature: float = 0.2) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        response = get_json(
            "https://api.groq.com/openai/v1/chat/completions",
            {"Authorization": f"Bearer {self.api_key}"},
            method="POST",
            json_body=payload,
        )
        if not isinstance(response, dict):
            raise ProviderError(f"Unexpected Groq response: {response}")

        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderError(f"Groq returned no choices: {response}")

        message = choices[0].get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(f"Groq returned no text content: {response}")
        return content.strip()
