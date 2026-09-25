"""Provider-backed orchestration for the active six-pair market scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.analysis.runner import OracleRunner
from app.analysis.scanner import DEFAULT_ACTIVE_INSTRUMENTS
from app.models.market_scan import MarketScan, PairAssessment
from app.models.oracle import OracleAnalysis


@dataclass(frozen=True, slots=True)
class MarketRunner:
    """Run the current active six-pair universe through the Oracle."""

    oracle: OracleRunner

    def scan(
        self,
        *,
        checked_at: datetime | None = None,
    ) -> tuple[MarketScan, tuple[OracleAnalysis, ...]]:
        now = checked_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")

        analyses = tuple(
            self.oracle.analyze_pair(instrument, checked_at=now)
            for instrument in DEFAULT_ACTIVE_INSTRUMENTS
        )
        return _build_scan(analyses), analyses


def _build_scan(analyses: tuple[OracleAnalysis, ...]) -> MarketScan:
    assessments = tuple(_assessment(analysis) for analysis in analyses)
    ranked = tuple(sorted(assessments, key=_ranking_key, reverse=True))
    return MarketScan(
        assessments=assessments,
        ranked=ranked,
        active_instruments=DEFAULT_ACTIVE_INSTRUMENTS,
    )


def _assessment(analysis: OracleAnalysis) -> PairAssessment:
    trade = analysis.trade
    return PairAssessment(
        instrument=analysis.instrument,
        decision=analysis.decision,
        weighted_score=analysis.weighted_score,
        risk_reward=(
            float(trade.risk_reward)
            if trade is not None and trade.risk_reward is not None
            else None
        ),
        direction=trade.direction if trade is not None else None,
        reasons=analysis.reasons,
    )


_DECISION_PRIORITY = {
    "TRADE": 5,
    "WATCH": 4,
    "WAIT": 3,
    "NO_TRADE": 2,
    "BLOCKED": 1,
}


def _ranking_key(candidate: PairAssessment) -> tuple[int, float, float, str]:
    return (
        _DECISION_PRIORITY[candidate.decision],
        candidate.weighted_score,
        candidate.risk_reward or 0.0,
        candidate.instrument,
    )
