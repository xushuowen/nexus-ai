"""Three-stream parallel processing: Think, Act, Remember."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """An event emitted by one of the three streams."""
    stream: str  # "think", "act", "remember"
    event_type: str  # e.g., "hypothesis", "action", "memory_store"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class ThreeStreamProcessor:
    """Manages parallel think/act/remember streams for the orchestrator.

    - Think: generates hypotheses and reasoning paths
    - Act: executes chosen actions (tool calls, agent dispatch)
    - Remember: stores important information to memory layers
    """

    def __init__(self) -> None:
        self._event_queue: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self._subscribers: list[asyncio.Queue[StreamEvent]] = []

    def subscribe(self) -> asyncio.Queue[StreamEvent]:
        """Subscribe to stream events (for WebSocket pushing)."""
        q: asyncio.Queue[StreamEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[StreamEvent]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def emit(self, event: StreamEvent) -> None:
        """Emit an event to all subscribers."""
        for sub in self._subscribers:
            try:
                sub.put_nowait(event)
            except asyncio.QueueFull:
                pass

    async def run_parallel(
        self,
        think_coro,
        act_coro,
        remember_coro,
    ) -> dict[str, Any]:
        """Run all three streams in parallel, collecting results."""
        results: dict[str, Any] = {}

        async def _wrap(name: str, coro):
            try:
                result = await coro
                results[name] = result
                await self.emit(StreamEvent(
                    stream=name,
                    event_type="completed",
                    content=str(result)[:200] if result else "",
                ))
            except Exception as e:
                logger.error(f"Stream '{name}' error: {e}")
                results[name] = None
                await self.emit(StreamEvent(
                    stream=name,
                    event_type="error",
                    content=str(e),
                ))

        await asyncio.gather(
            _wrap("think", think_coro),
            _wrap("act", act_coro),
            _wrap("remember", remember_coro),
        )
        return results

    async def event_stream(self) -> AsyncIterator[StreamEvent]:
        """Async iterator for consuming events."""
        q = self.subscribe()
        try:
            while True:
                event = await q.get()
                yield event
        finally:
            self.unsubscribe(q)
