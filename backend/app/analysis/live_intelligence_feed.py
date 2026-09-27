"""Connect a live news stream to the bounded intelligence buffer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.analysis.live_intelligence_buffer import LiveIntelligenceBuffer
from app.models.fundamental import NewsItem


@dataclass(frozen=True, slots=True)
class LiveIntelligenceFeed:
    """Route streamed headlines into classified, bounded live intelligence."""

    buffer: LiveIntelligenceBuffer

    def consume(
        self,
        stream: Callable[[Callable[[NewsItem], None]], None],
    ) -> None:
        """Consume a news stream until the stream exits."""
        stream(self.buffer.add)
