"""Text reporting for completed market scans."""

from __future__ import annotations

from app.models.market_scan import MarketScan, PairAssessment


def render_market_report(scan: MarketScan) -> str:
    """Render a concise human-readable report from an existing market scan."""
    lines = [
        "TRADE ORACLE MARKET REPORT",
        f"Active universe: {', '.join(scan.active_instruments)}",
        "",
        "RANKED PAIRS",
    ]

    for index, assessment in enumerate(scan.ranked, start=1):
        lines.extend(_format_assessment(index, assessment))

    if scan.ranked:
        lines.extend(
            [
                "",
                f"TOP RESULT: {scan.ranked[0].instrument} "
                f"({scan.ranked[0].decision})",
            ]
        )

    return "\n".join(lines)


def _format_assessment(index: int, assessment: PairAssessment) -> tuple[str, ...]:
    direction = assessment.direction or "N/A"
    score = f"{assessment.weighted_score:.3f}"
    rr = f"{assessment.risk_reward:.2f}" if assessment.risk_reward is not None else "N/A"
    summary = (
        f"{index}. {assessment.instrument} | {assessment.decision} | "
        f"score={score} | direction={direction} | RR={rr}"
    )
    return (summary, *assessment.reasons)
