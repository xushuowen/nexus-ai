"""Memory consolidation daemon - periodically organizes and strengthens memories.
Runs in background, all operations are local (0 token cost)."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from nexus import config

if TYPE_CHECKING:
    from nexus.memory.hybrid_store import HybridMemory

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """Background task that periodically consolidates memory layers.

    Operations (all local, 0 tokens):
    1. Decay working memory attention weights
    2. Decay knowledge graph node activations
    3. Clean up low-confidence procedural memories
    4. Promote frequently accessed episodic memories to semantic
    """

    def __init__(self, memory: HybridMemory) -> None:
        self.memory = memory
        self.interval = config.get("memory.consolidation_interval_minutes", 30) * 60
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the consolidation daemon."""
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(f"Memory consolidation daemon started (interval: {self.interval}s)")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self.consolidate()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consolidation error: {e}")

    async def consolidate(self) -> dict[str, int]:
        """Run a single consolidation cycle."""
        stats = {}

        # 1. Decay working memory
        self.memory.working.decay_all(rate=0.1)
        stats["working_slots"] = self.memory.working.size

        # 2. Decay knowledge graph
        if self.memory.kg:
            removed = await self.memory.kg.decay()
            stats["kg_nodes_removed"] = removed

        # 3. Clean procedural memory
        if self.memory.procedural:
            cleaned = await self.memory.procedural.cleanup(min_confidence=0.2)
            stats["procedures_cleaned"] = cleaned

        # 4. Promote high-value episodic to semantic
        if self.memory.episodic and self.memory.fts:
            lessons = await self.memory.episodic.get_lessons(limit=5)
            promoted = 0
            for lesson in lessons:
                if lesson and len(lesson) > 10:
                    await self.memory.fts.store(
                        title="Lesson",
                        content=lesson,
                        category="episodic_promotion",
                        source="consolidation",
                    )
                    promoted += 1
            stats["lessons_promoted"] = promoted

        logger.info(f"Consolidation complete: {stats}")
        return stats

    async def force_consolidate(self) -> dict[str, int]:
        """Manually trigger consolidation."""
        return await self.consolidate()
