"""Small standard-library HTTP client so provider adapters stay dependency-light."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ProviderError(RuntimeError):
    """Raised when an external data provider cannot be queried safely."""


def get_json(
    base_url: str,
    params: dict[str, str | int],
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
) -> object:
    query = urlencode(params)
    request = Request(
        f"{base_url}?{query}",
        headers={"Accept": "application/json", **(headers or {})},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ProviderError(f"Provider request failed: {exc}") from exc

    if isinstance(payload, dict) and (
        "code" in payload and payload.get("code") not in (200, "200")
    ):
        raise ProviderError(str(payload))
    return payload
