from datetime import UTC, datetime
from decimal import Decimal

import pytest

import app.analysis.llm as llm_module
import app.data.fred as fred_module
from app.analysis.llm import GroqReasoner
from app.data.fred import FREDProvider, MacroObservation
from app.data.http import ProviderError


def test_fred_parses_observations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fred_module,
        "get_json",
        lambda *args, **kwargs: {
            "observations": [
                {"date": "2026-09-24", "value": "3.25"},
                {"date": "2026-09-23", "value": "."},
            ]
        },
    )
    provider = FREDProvider("test-key")
    result = provider.get_observations("DFF")
    assert result == [
        MacroObservation(
            series_id="DFF",
            date=datetime(2026, 9, 24, tzinfo=UTC),
            value=Decimal("3.25"),
        )
    ]


def test_fred_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        FREDProvider()


def test_groq_returns_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_module,
        "get_json",
        lambda *args, **kwargs: {
            "choices": [{"message": {"content": "Structured market summary."}}]
        },
    )
    reasoner = GroqReasoner("test-key")
    assert reasoner.complete(system="Be concise.", user="Summarize this.") == (
        "Structured market summary."
    )
