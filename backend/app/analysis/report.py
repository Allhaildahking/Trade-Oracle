"""Deterministic text reporting for market scans."""

from __future__ import annotations

from app.models.market_scan import MarketScan


def render_market_scan(scan: MarketScan) -> str:
    """Render a concise market snapshot suitable for logs or Telegram."""
    lines = ["TRADE ORACLE | MARKET SCAN", ""]
    for index, item in enumerate(scan.ranked, start=1):
        direction = f" {item.direction}" if item.direction else ""
        rr = f" RR {item.risk_reward:.2f}" if item.risk_reward is not None else ""
        lines.append(
            f"{index}. {item.instrument} | {item.decision}{direction} "
            f"| score {item.weighted_score:.3f}{rr}"
        )
    return "\n".join(lines)
