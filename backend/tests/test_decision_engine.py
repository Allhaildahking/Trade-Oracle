from datetime import UTC, datetime
from decimal import Decimal

from app.analysis.decision import DECISION_THRESHOLD, DecisionContext, decide
from app.models.confirmation import Confirmation5M
from app.models.fundamental import CurrencyBias, PairBias
from app.models.risk import RiskValidation
from app.models.setup import SetupCandidate
from app.models.trade import TradeCandidate


def _setup(status: str = "CANDIDATE") -> SetupCandidate:
    return SetupCandidate(
        instrument="EURUSD",
        timeframe="15M",
        direction="BUY",
        status=status,
        fundamental_score=Decimal("0.90"),
        regime=None,
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=(),
    )


def _confirmation(status: str = "CONFIRMED") -> Confirmation5M:
    return Confirmation5M(
        instrument="EURUSD",
        timeframe="5M",
        direction="BUY",
        status=status,
        structure_events=(),
        displacement=None,
        sweep=None,
        reasons=(),
    )


def _trade(rr: str = "2.5", status: str = "VALID") -> TradeCandidate:
    return TradeCandidate(
        instrument="EURUSD",
        direction="BUY",
        status=status,
        entry=Decimal("1.1000"),
        stop_loss=Decimal("1.0980"),
        take_profit=Decimal("1.1050"),
        risk_distance=Decimal("0.0020"),
        reward_distance=Decimal("0.0050"),
        risk_reward=Decimal(rr),
        invalidation=Decimal("1.0980"),
        reasons=(),
    )


def _risk(decision: str = "TRADE", valid: bool = True) -> RiskValidation:
    return RiskValidation(
        instrument="EURUSD",
        decision=decision,
        valid=valid,
        reasons=(),
        checked_at=datetime(2026, 9, 25, 1, 0, tzinfo=UTC),
    )


def _context(**overrides: object) -> DecisionContext:
    values = {
        "fundamental_score": 0.9,
        "technical_score": 0.9,
        "setup": _setup(),
        "confirmation": _confirmation(),
        "trade": _trade(),
        "risk": _risk(),
    }
    values.update(overrides)
    return DecisionContext(**values)


def test_weighted_score_uses_51_49() -> None:
    context = _context(fundamental_score=1.0, technical_score=0.0)
    assert context.weighted_score == 0.51


def test_full_valid_pipeline_produces_trade() -> None:
    assert decide(_context()) == "TRADE"


def test_news_block_has_priority() -> None:
    assert decide(_context(news_blocked=True)) == "BLOCKED"


def test_risk_block_has_priority() -> None:
    assert decide(_context(risk=_risk("BLOCKED", False))) == "BLOCKED"


def test_missing_quote_waits_at_risk_layer() -> None:
    assert decide(_context(risk=_risk("WAIT", False))) == "WAIT"


def test_candidate_without_confirmation_is_watch() -> None:
    assert decide(_context(confirmation=_confirmation("REJECTED"))) == "WATCH"


def test_rejected_setup_is_no_trade() -> None:
    assert decide(_context(setup=_setup("REJECTED"))) == "NO_TRADE"


def test_rr_below_minimum_is_no_trade() -> None:
    assert decide(_context(trade=_trade("2.49"))) == "NO_TRADE"


def test_score_below_threshold_is_no_trade() -> None:
    context = _context(fundamental_score=0.50, technical_score=0.50)
    assert context.weighted_score < DECISION_THRESHOLD
    assert decide(context) == "NO_TRADE"


def test_invalid_scores_are_rejected() -> None:
    try:
        decide(_context(fundamental_score=1.1))
    except ValueError as exc:
        assert "fundamental_score" in str(exc)
    else:
        raise AssertionError("invalid fundamental score was accepted")


def test_decision_context_can_build_from_pair_bias() -> None:
    pair_bias = PairBias(
        instrument="EURUSD",
        base=CurrencyBias(
            "EUR", Decimal("8"), ()
        ),
        quote=__import__("app.models.fundamental", fromlist=["CurrencyBias"]).CurrencyBias(
            "USD", Decimal("0"), ()
        ),
        score=Decimal("8"),
        direction="BUY",
        evidence=(),
    )
    context = DecisionContext.from_pair_bias(pair_bias, technical_score=0.8)
    assert context.fundamental_score == 0.8
    assert context.weighted_score == 0.8
