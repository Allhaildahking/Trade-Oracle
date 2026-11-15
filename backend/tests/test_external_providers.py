from datetime import UTC, datetime
from decimal import Decimal

import pytest

import app.analysis.llm as llm_module
from app.analysis.llm import GroqReasoner
import app.data.fred as fred_module
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



def test_alpha_vantage_requests_gold_market_news_and_tags_gold_headlines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.data.alpha_vantage as alpha_module
    from app.data.alpha_vantage import AlphaVantageNewsProvider

    captured: dict[str, object] = {}

    def fake_get_json(url, params):
        captured.update(params)
        return {
            "feed": [
                {
                    "url": "https://example.com/gold",
                    "time_published": "20260925T120000",
                    "title": "Central banks increase gold purchases",
                    "summary": "Bullion demand rises.",
                    "source": "Reuters",
                    "topics": [{"topic": "forex:usd"}],
                },
                {
                    "url": "https://example.com/tech",
                    "time_published": "20260925T110000",
                    "title": "Technology shares rally",
                    "summary": "A broad equity-market session.",
                    "source": "Reuters",
                    "topics": [{"topic": "forex:usd"}],
                },
            ]
        }

    monkeypatch.setattr(alpha_module, "get_json", fake_get_json)
    items = AlphaVantageNewsProvider("test-key").get_news(
        currencies=("XAU", "USD"),
        start=datetime(2026, 9, 25, tzinfo=UTC),
        end=datetime(2026, 9, 26, tzinfo=UTC),
    )

    assert captured["topics"] == "forex:usd,financial_markets"
    assert "XAU" in items[0].currencies
    assert "XAU" not in items[1].currencies
