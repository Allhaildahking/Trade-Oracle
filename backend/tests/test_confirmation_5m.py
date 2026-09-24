from datetime import UTC, datetime
from decimal import Decimal

from app.analysis import confirmation_5m
from app.models.confirmation import Confirmation5M
from app.models.displacement import Displacement
from app.models.regime import RegimeSnapshot
from app.models.setup import SetupCandidate
from app.models.structure import StructureEvent, StructureSnapshot


def candle():
    from app.models.market import Candle

    return Candle(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, tzinfo=UTC),
        open=Decimal("1.1000"),
        high=Decimal("1.1020"),
        low=Decimal("1.0980"),
        close=Decimal("1.1015"),
    )


def setup_candidate() -> SetupCandidate:
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
        direction="BUY",
        status="CANDIDATE",
        fundamental_score=Decimal("3"),
        regime=regime,
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=("aligned",),
    )


def test_confirms_aligned_5m_structure_and_displacement(monkeypatch) -> None:
    event = StructureEvent(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, 5, tzinfo=UTC),
        price=Decimal("1.1010"),
        kind="BOS",
        direction="BULLISH",
        broken_swing=object(),
    )
    displacement = Displacement(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, 10, tzinfo=UTC),
        direction="BULLISH",
        body=Decimal("0.0010"),
        range=Decimal("0.0014"),
        body_ratio=Decimal("0.71"),
        average_body=Decimal("0.0004"),
        close_location=Decimal("0.90"),
    )

    monkeypatch.setattr(
        confirmation_5m,
        "detect_structure",
        lambda _: StructureSnapshot((), (event,)),
    )
    monkeypatch.setattr(
        confirmation_5m,
        "detect_displacements",
        lambda _: (displacement,),
    )
    monkeypatch.setattr(confirmation_5m, "detect_liquidity_sweeps", lambda _, levels: ())

    result = confirmation_5m.confirm_5m([candle()], setup=setup_candidate())

    assert isinstance(result, Confirmation5M)
    assert result.status == "CONFIRMED"
    assert result.direction == "BUY"
    assert result.displacement == displacement
    assert result.sweep is None


def test_rejects_5m_when_structure_conflicts(monkeypatch) -> None:
    event = StructureEvent(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, 5, tzinfo=UTC),
        price=Decimal("1.0990"),
        kind="CHoCH",
        direction="BEARISH",
        broken_swing=object(),
    )
    displacement = Displacement(
        instrument="EURUSD",
        timeframe="5M",
        timestamp=datetime(2026, 1, 2, 12, 10, tzinfo=UTC),
        direction="BEARISH",
        body=Decimal("0.0010"),
        range=Decimal("0.0014"),
        body_ratio=Decimal("0.71"),
        average_body=Decimal("0.0004"),
        close_location=Decimal("0.10"),
    )

    monkeypatch.setattr(
        confirmation_5m,
        "detect_structure",
        lambda _: StructureSnapshot((), (event,)),
    )
    monkeypatch.setattr(
        confirmation_5m,
        "detect_displacements",
        lambda _: (displacement,),
    )
    monkeypatch.setattr(confirmation_5m, "detect_liquidity_sweeps", lambda _, levels: ())

    result = confirmation_5m.confirm_5m([candle()], setup=setup_candidate())

    assert result.status == "REJECTED"
    assert result.direction == "BUY"
    assert result.displacement is None
    assert result.structure_events == ()


def test_rejects_non_candidate_setup() -> None:
    setup = setup_candidate()
    rejected = SetupCandidate(
        instrument=setup.instrument,
        timeframe=setup.timeframe,
        direction=setup.direction,
        status="REJECTED",
        fundamental_score=setup.fundamental_score,
        regime=setup.regime,
        structure_events=(),
        sweep=None,
        displacement=None,
        break_retest=None,
        reasons=("rejected",),
    )

    import pytest

    with pytest.raises(ValueError, match="CANDIDATE"):
        confirmation_5m.confirm_5m([candle()], setup=rejected)
