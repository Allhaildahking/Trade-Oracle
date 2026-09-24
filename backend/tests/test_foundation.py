from datetime import UTC, datetime

import pytest

from app.analysis.decision import DecisionContext, decide
from app.core.constants import (
    CORE_INSTRUMENTS,
    FUNDAMENTAL_WEIGHT,
    MINIMUM_RR,
    TECHNICAL_WEIGHT,
)
from app.models.signal import Direction, Signal

def test_v1_core_instruments() -> None:
    assert CORE_INSTRUMENTS == (
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "XAUUSD",
    )


def test_weighting_rule() -> None:
    assert FUNDAMENTAL_WEIGHT == 0.51
    assert TECHNICAL_WEIGHT == 0.49
    assert FUNDAMENTAL_WEIGHT + TECHNICAL_WEIGHT == 1.0


def test_minimum_rr_is_2_5() -> None:
    assert MINIMUM_RR == 2.5


def test_signal_calculates_rr() -> None:
    signal = Signal(
        instrument="EURUSD",
        direction=Direction.BUY,
        entry=1.1000,
        stop_loss=1.0970,
        take_profit=1.1075,
        confidence=0.80,
        created_at=datetime.now(UTC),
    )

    assert signal.risk_distance == pytest.approx(0.0030)
    assert signal.reward_distance == pytest.approx(0.0075)
    assert signal.rr == pytest.approx(2.5)


def test_foundation_never_fakes_a_trade() -> None:
    decision = decide(
        DecisionContext(
            fundamental_score=0.90,
            technical_score=0.90,
        )
    )
    assert decision == "NO_TRADE"


def test_news_block_blocks_decision() -> None:
    decision = decide(
        DecisionContext(
            fundamental_score=0.90,
            technical_score=0.90,
            news_blocked=True,
        )
    )
    assert decision == "BLOCKED"


def test_invalid_scores_are_rejected() -> None:
    with pytest.raises(ValueError):
        decide(DecisionContext(fundamental_score=1.1, technical_score=0.5))
