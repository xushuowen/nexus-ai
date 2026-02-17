"""Async FIFO message queue with debouncing for the orchestrator."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class QueueItem:
    payload: Any
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # Higher = processed first
    source: str = ""


class MessageQueue:
    """Async priority queue with debounce support."""

    def __init__(self, debounce_ms: int = 300) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, float, QueueItem]] = asyncio.PriorityQueue()
        self._debounce_s = debounce_ms / 1000.0
        self._last_enqueue: dict[str, float] = {}
        self._processing = False

    async def put(self, item: QueueItem) -> None:
        """Add item to queue with optional debouncing per source."""
        now = time.time()
        source = item.source or "default"
        last = self._last_enqueue.get(source, 0)
        if now - last < self._debounce_s:
            # Debounce: skip if too frequent from same source
            return
        self._last_enqueue[source] = now
        # PriorityQueue sorts by first element (lower = higher priority)
        await self._queue.put((-item.priority, item.timestamp, item))

    async def get(self) -> QueueItem:
        """Get next item from queue (blocks until available)."""
        _, _, item = await self._queue.get()
        return item

    def empty(self) -> bool:
        return self._queue.empty()

    @property
    def size(self) -> int:
        return self._queue.qsize()

    async def process_loop(self, handler: Callable[[QueueItem], Awaitable[None]]) -> None:
        """Continuously process queue items."""
        self._processing = True
        while self._processing:
            try:
                item = await asyncio.wait_for(self.get(), timeout=1.0)
                await handler(item)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Queue handler error: {e}")

    def stop(self) -> None:
        self._processing = False
