"""Provider-backed orchestration for the active six-pair market scan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.analysis.rotation import RotationDecision
from app.analysis.runner import OracleRunner
from app.analysis.scanner import DEFAULT_ACTIVE_INSTRUMENTS, active_universe, scan_analyses
from app.models.market_scan import MarketScan
from app.models.oracle import OracleAnalysis


@dataclass(frozen=True, slots=True)
class MarketRunner:
    """Run the complete Oracle across the active six-pair universe."""

    oracle: OracleRunner

    def scan(
        self,
        *,
        checked_at: datetime | None = None,
        rotation: RotationDecision | None = None,
    ) -> tuple[MarketScan, tuple[OracleAnalysis, ...]]:
        now = checked_at or datetime.now(UTC)
        if now.tzinfo is None:
            raise ValueError("checked_at must be timezone-aware")

        instruments = (
            active_universe(rotation)
            if rotation is not None
            else DEFAULT_ACTIVE_INSTRUMENTS
        )
        analyses = tuple(
            self.oracle.analyze_pair(instrument, checked_at=now)
            for instrument in instruments
        )
        return scan_analyses(analyses, active_instruments=instruments), analyses
