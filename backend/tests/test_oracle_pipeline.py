from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.oracle import analyze_pair
from app.models.confirmation import Confirmation5M
from app.models.fundamental import CurrencyBias, PairBias
from app.models.regime import RegimeSnapshot
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate


def _bias() -> PairBias:
    return PairBias(
        instrument="EURUSD",
        base=CurrencyBias("EUR", Decimal("8"), ()),
        quote=CurrencyBias("USD", Decimal("0"), ()),
        score=Decimal("8"),
        direction="BUY",
        evidence=(),
    )


def _setup() -> SetupCandidate:
    return SetupCandidate(
        instrument="EURUSD",
        timeframe="15M",
        direction="BUY",
        status="CANDIDATE",
        fundamental_score=Decimal("8"),
        regime=RegimeSnapshot(
            instrument="EURUSD",
            timeframe="15M",
            regime="TRENDING",
            atr=1.0,
            baseline_atr=1.0,
            volatility_ratio=1.0,
            directional_efficiency=0.8,
            range_to_atr=2.5,
            sample_size=20,
        ),
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=("candidate",),
    )


def _confirmation() -> Confirmation5M:
    return Confirmation5M(
        instrument="EURUSD",
        timeframe="5M",
        direction="BUY",
        status="CONFIRMED",
        structure_events=(),
        displacement=None,
        sweep=None,
        reasons=("confirmed",),
    )


def _trade() -> TradeCandidate:
    return TradeCandidate(
        instrument="EURUSD",
        direction="BUY",
        status="VALID",
        entry=Decimal("1.1000"),
        stop_loss=Decimal("1.0980"),
        take_profit=Decimal("1.1050"),
        risk_distance=Decimal("0.0020"),
        reward_distance=Decimal("0.0050"),
        risk_reward=Decimal("2.5"),
        invalidation=Decimal("1.0980"),
        reasons=("valid",),
    )


def _risk() -> RiskValidation:
    return RiskValidation(
        instrument="EURUSD",
        decision="TRADE",
        valid=True,
        reasons=("validated",),
        checked_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
    )


def test_pipeline_connects_the_decision_chain(monkeypatch) -> None:
    import app.analysis.oracle as oracle

    monkeypatch.setattr(oracle, "detect_structure", lambda candles: object())
    monkeypatch.setattr(
        oracle,
        "detect_setup_candidate",
        lambda candles, **kwargs: _setup(),
    )
    monkeypatch.setattr(
        oracle,
        "confirm_5m",
        lambda candles, **kwargs: _confirmation(),
    )
    monkeypatch.setattr(
        oracle,
        "construct_trade",
        lambda **kwargs: _trade(),
    )
    monkeypatch.setattr(
        oracle,
        "validate_trade",
        lambda **kwargs: _risk(),
    )
    monkeypatch.setattr(oracle, "_setup_score", lambda setup: 0.65)
    monkeypatch.setattr(oracle, "_technical_score", lambda setup, confirmation: 1.0)

    result = oracle.analyze_pair(
        candles_4h=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "4H"})()],
        candles_1h=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "1H"})()],
        candles_15m=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "15M"})()],
        candles_5m=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "5M"})()],
        pair_bias=_bias(),
        checked_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
    )

    assert result.decision == "TRADE"
    assert result.technical_score == 1.0
    assert result.weighted_score == 0.898
    assert result.setup is not None
    assert result.confirmation is not None
    assert result.trade is not None
    assert result.risk is not None


def test_pipeline_rejects_wrong_instrument() -> None:
    try:
        analyze_pair(
            candles_4h=[type("CandleStub", (), {"instrument": "GBPUSD", "timeframe": "4H"})()],
            candles_1h=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "1H"})()],
            candles_15m=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "15M"})()],
            candles_5m=[type("CandleStub", (), {"instrument": "EURUSD", "timeframe": "5M"})()],
            pair_bias=_bias(),
            checked_at=datetime(2026, 9, 25, 8, tzinfo=UTC),
        )
    except ValueError as exc:
        assert "4H" in str(exc)
    else:
        raise AssertionError("wrong instrument was accepted")
