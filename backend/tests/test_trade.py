from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.analysis.trade import construct_trade
from app.models.confirmation import Confirmation5M
from app.models.liquidity import LiquidityLevel
from app.models.liquidity_sweep import LiquiditySweep
from app.models.regime import RegimeSnapshot
from app.models.setup import SetupCandidate
from app.models.structure import StructureEvent
def make_setup(direction: str = "BUY", sweep_price: str = "1.0980") -> SetupCandidate:
    level = LiquidityLevel(
        instrument="EURUSD",
        timeframe="15M",
        kind="PREVIOUS_DAY_LOW" if direction == "BUY" else "PREVIOUS_DAY_HIGH",
        side="SELL_SIDE" if direction == "BUY" else "BUY_SIDE",
        price=Decimal(sweep_price),
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 2, tzinfo=UTC),
        label="setup invalidation",
    )
    sweep = LiquiditySweep(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=level.period_end,
        direction="BULLISH" if direction == "BUY" else "BEARISH",
        level=level,
        sweep_price=Decimal(sweep_price),
        close_price=Decimal("1.1010" if direction == "BUY" else "1.0990"),
    )
    regime = RegimeSnapshot(
        instrument="EURUSD",
        timeframe="15M",
        regime="TRENDING",
        atr=0.001,
        baseline_atr=0.001,
        volatility_ratio=1.0,
        directional_efficiency=0.8,
        range_to_atr=3.0,
        sample_size=20,
    )
    return SetupCandidate(
        instrument="EURUSD",
        timeframe="15M",
        direction=direction,
        status="CANDIDATE",
        fundamental_score=Decimal("3"),
        regime=regime,
        structure_events=(),
        sweep=sweep,
        displacement=None,
        break_retest=None,
        reasons=("aligned",),
    )


def make_confirmation(direction: str = "BUY", entry: str = "1.1010") -> Confirmation5M:
    event = StructureEvent(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, 5, tzinfo=UTC),
        price=Decimal(entry),
        kind="BOS",
        direction="BULLISH" if direction == "BUY" else "BEARISH",
        broken_swing=object(),
    )
    return Confirmation5M(
        instrument="EURUSD",
        timeframe="5M",
        direction=direction,
        status="CONFIRMED",
        structure_events=(event,),
        displacement=None,
        sweep=None,
        reasons=("confirmed",),
    )


def test_constructs_buy_trade_at_minimum_rr() -> None:
    result = construct_trade(setup=make_setup(), confirmation=make_confirmation())

    assert result.status == "VALID"
    assert result.entry == Decimal("1.1010")
    assert result.stop_loss == Decimal("1.0980")
    assert result.take_profit == Decimal("1.1085")
    assert result.risk_distance == Decimal("0.0030")
    assert result.risk_reward == Decimal("2.5")


def test_constructs_sell_trade_at_minimum_rr() -> None:
    result = construct_trade(
        setup=make_setup("SELL", "1.1020"),
        confirmation=make_confirmation("SELL", "1.0990"),
    )

    assert result.status == "VALID"
    assert result.take_profit == Decimal("1.0915")
    assert result.risk_reward == Decimal("2.5")


def test_rejects_missing_invalidation_anchor() -> None:
    setup = make_setup()
    setup = SetupCandidate(
        instrument=setup.instrument,
        timeframe=setup.timeframe,
        direction=setup.direction,
        status=setup.status,
        fundamental_score=setup.fundamental_score,
        regime=setup.regime,
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=setup.reasons,
    )
    result = construct_trade(setup=setup, confirmation=make_confirmation())
    assert result.status == "REJECTED"


def test_rejects_unconfirmed_confirmation() -> None:
    confirmation = make_confirmation()
    rejected = Confirmation5M(
        instrument=confirmation.instrument,
        timeframe=confirmation.timeframe,
        direction=confirmation.direction,
        status="REJECTED",
        structure_events=confirmation.structure_events,
        displacement=None,
        sweep=None,
        reasons=("rejected",),
    )
    with pytest.raises(ValueError, match="CONFIRMED"):
        construct_trade(setup=make_setup(), confirmation=rejected)
