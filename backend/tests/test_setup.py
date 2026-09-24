from datetime import UTC, datetime
from decimal import Decimal

from app.analysis import setup as setup_analysis
from app.models.break_retest import BreakRetest
from app.models.displacement import Displacement
from app.models.fundamental import CurrencyBias, PairBias
from app.models.liquidity import LiquidityLevel
from app.models.liquidity_sweep import LiquiditySweep
from app.models.market import Candle
from app.models.regime import RegimeSnapshot
from app.models.structure import StructureEvent, StructureSnapshot


def candle() -> Candle:
    timestamp = datetime(2026, 1, 2, 12, tzinfo=UTC)
    return Candle(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=timestamp,
        open=Decimal("1.1000"),
        high=Decimal("1.1020"),
        low=Decimal("1.0980"),
        close=Decimal("1.1015"),
    )


def pair_bias(direction: str) -> PairBias:
    base = CurrencyBias("EUR", Decimal("2"), ("EUR strength",))
    quote = CurrencyBias("USD", Decimal("-1"), ("USD weakness",))
    return PairBias("EURUSD", base, quote, Decimal("3"), direction, ("aligned",))


def structure_snapshot() -> StructureSnapshot:
    event = StructureEvent(
        instrument="EURUSD",
        timeframe="1H",
        timestamp=datetime(2026, 1, 2, 11, tzinfo=UTC),
        price=Decimal("1.1000"),
        kind="BOS",
        direction="BULLISH",
        broken_swing=object(),
    )
    return StructureSnapshot(swings=(), events=(event,))


def test_builds_candidate_when_all_evidence_aligns(monkeypatch) -> None:
    level = LiquidityLevel(
        instrument="EURUSD",
        timeframe="15M",
        kind="PREVIOUS_DAY_LOW",
        side="SELL_SIDE",
        price=Decimal("1.0990"),
        period_start=datetime(2026, 1, 1, tzinfo=UTC),
        period_end=datetime(2026, 1, 2, tzinfo=UTC),
        label="Previous day low",
    )
    sweep = LiquiditySweep(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=datetime(2026, 1, 2, 12, tzinfo=UTC),
        direction="BULLISH",
        level=level,
        sweep_price=Decimal("1.0985"),
        close_price=Decimal("1.1015"),
    )
    displacement = Displacement(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=datetime(2026, 1, 2, 12, tzinfo=UTC),
        direction="BULLISH",
        body=Decimal("0.0015"),
        range=Decimal("0.0020"),
        body_ratio=Decimal("0.75"),
        average_body=Decimal("0.0005"),
        close_location=Decimal("0.875"),
    )
    break_retest = BreakRetest(
        instrument="EURUSD",
        timeframe="15M",
        timestamp=datetime(2026, 1, 2, 12, 15, tzinfo=UTC),
        direction="BULLISH",
        level=Decimal("1.1000"),
        break_price=Decimal("1.1015"),
        retest_price=Decimal("1.1000"),
        close_price=Decimal("1.1010"),
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

    monkeypatch.setattr(setup_analysis, "detect_regime", lambda _: regime)
    monkeypatch.setattr(setup_analysis, "detect_structure", lambda _: StructureSnapshot((), ()))
    monkeypatch.setattr(setup_analysis, "detect_liquidity_sweeps", lambda _, levels: (sweep,))
    monkeypatch.setattr(setup_analysis, "detect_displacements", lambda _: (displacement,))
    monkeypatch.setattr(
        setup_analysis,
        "detect_break_retests",
        lambda _, levels, tolerance: (break_retest,),
    )

    result = setup_analysis.detect_setup_candidate(
        [candle()],
        pair_bias=pair_bias("BUY"),
        htf_structure=(structure_snapshot(),),
        liquidity_levels=(level,),
    )

    assert result.status == "CANDIDATE"
    assert result.direction == "BUY"
    assert result.sweep == sweep
    assert result.displacement == displacement
    assert result.break_retest == break_retest
    assert result.fundamental_score == Decimal("3")


def test_rejects_neutral_fundamental_bias(monkeypatch) -> None:
    regime = RegimeSnapshot(
        instrument="EURUSD",
        timeframe="15M",
        regime="RANGING",
        atr=0.001,
        baseline_atr=0.001,
        volatility_ratio=1.0,
        directional_efficiency=0.2,
        range_to_atr=1.5,
        sample_size=20,
    )
    monkeypatch.setattr(setup_analysis, "detect_regime", lambda _: regime)
    monkeypatch.setattr(setup_analysis, "detect_structure", lambda _: StructureSnapshot((), ()))
    monkeypatch.setattr(setup_analysis, "detect_liquidity_sweeps", lambda _, levels: ())
    monkeypatch.setattr(setup_analysis, "detect_displacements", lambda _: ())
    monkeypatch.setattr(setup_analysis, "detect_break_retests", lambda _, levels, tolerance: ())

    result = setup_analysis.detect_setup_candidate(
        [candle()],
        pair_bias=pair_bias("NEUTRAL"),
    )

    assert result.status == "REJECTED"
    assert result.direction == "NEUTRAL"
