from decimal import Decimal

import pytest

from app.execution.position_sizing import calculate_position_size
from app.models.symbol import SymbolSpec


@pytest.fixture
def micro_spec():
    return SymbolSpec(
        instrument="XAUUSDmicro",
        trade_tick_size=Decimal("0.01"),
        trade_tick_value_loss=Decimal("0.01"),
        volume_min=Decimal("0.1"),
        volume_max=Decimal("100"),
        volume_step=Decimal("0.1"),
        contract_size=Decimal("1"),
    )


def test_sizes_down_to_volume_step_without_exceeding_budget(micro_spec):
    result = calculate_position_size(
        equity=Decimal("30"),
        risk_percent=Decimal("1"),
        direction="BUY",
        entry=Decimal("2350"),
        stop_loss=Decimal("2349"),
        spec=micro_spec,
    )

    assert result.accepted
    assert result.volume == Decimal("0.3")
    assert result.estimated_loss == Decimal("0.30")
    assert result.estimated_loss <= result.risk_budget


def test_rejects_when_minimum_volume_exceeds_risk_budget(micro_spec):
    result = calculate_position_size(
        equity=Decimal("1"),
        risk_percent=Decimal("0.5"),
        direction="BUY",
        entry=Decimal("2350"),
        stop_loss=Decimal("2349"),
        spec=micro_spec,
    )

    assert not result.accepted
    assert result.volume is None
    assert "minimum broker volume" in result.reason


def test_rejects_wrong_side_stop(micro_spec):
    with pytest.raises(ValueError, match="below entry"):
        calculate_position_size(
            equity=Decimal("30"),
            risk_percent=Decimal("1"),
            direction="BUY",
            entry=Decimal("2350"),
            stop_loss=Decimal("2351"),
            spec=micro_spec,
        )


def test_rounds_down_instead_of_nearest(micro_spec):
    result = calculate_position_size(
        equity=Decimal("30"),
        risk_percent=Decimal("1"),
        direction="SELL",
        entry=Decimal("2350"),
        stop_loss=Decimal("2350.55"),
        spec=micro_spec,
    )

    assert result.accepted
    assert result.volume == Decimal("0.5")
    assert result.estimated_loss <= result.risk_budget


def test_rejects_risk_above_two_percent(micro_spec):
    with pytest.raises(ValueError, match="at most 2"):
        calculate_position_size(
            equity=Decimal("30"),
            risk_percent=Decimal("2.1"),
            direction="BUY",
            entry=Decimal("2350"),
            stop_loss=Decimal("2349"),
            spec=micro_spec,
        )


def test_rejects_unknown_direction(micro_spec):
    with pytest.raises(ValueError, match="direction must be BUY or SELL"):
        calculate_position_size(
            equity=Decimal("30"),
            risk_percent=Decimal("1"),
            direction="HOLD",
            entry=Decimal("2350"),
            stop_loss=Decimal("2349"),
            spec=micro_spec,
        )
