"""Budget-controlled Curiosity Engine - intrinsic motivation system.
Performs self-directed exploration only when budget allows."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, TYPE_CHECKING

from nexus import config
from nexus.core.budget import BudgetController

if TYPE_CHECKING:
    from nexus.memory.hybrid_store import HybridMemory
    from nexus.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class CuriosityEngine:
    """Autonomous exploration system that respects daily budget limits.

    Free operations (always allowed):
    - Knowledge graph reorganization
    - Memory decay computation
    - Local contradiction detection
    - Pattern analysis in stored data

    Budget-controlled operations (requires budget check):
    - LLM-based knowledge gap analysis
    - Concept explanation generation
    - Self-questioning and answering
    """

    def __init__(
        self,
        budget: BudgetController,
        memory: HybridMemory | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.budget = budget
        self.memory = memory
        self.llm = llm
        self._task: asyncio.Task | None = None
        self._running = False
        self._pending_explorations: list[dict[str, Any]] = []
        self._exploration_log: list[dict[str, Any]] = []

    async def start(self, interval_seconds: int = 300) -> None:
        """Start the curiosity daemon."""
        self._running = True
        self._task = asyncio.create_task(self._loop(interval_seconds))
        logger.info("Curiosity engine started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self, interval: int) -> None:
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self.tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Curiosity tick error: {e}")

    async def tick(self) -> dict[str, Any]:
        """Run one curiosity cycle."""
        results = {}

        # Free operations (always run)
        results["free_ops"] = await self._free_operations()

        # Budget-controlled operations
        if self.budget.curiosity_ops_remaining > 0 and self.llm:
            results["budget_ops"] = await self._budget_operations()

        return results

    async def _free_operations(self) -> dict[str, Any]:
        """Operations that cost 0 tokens."""
        stats = {}

        if not self.memory:
            return stats

        # 1. Knowledge graph reorganization
        try:
            if self.memory.kg:
                removed = await self.memory.kg.decay(rate=0.005)
                stats["kg_decay_removed"] = removed
        except Exception as e:
            logger.debug(f"KG decay error: {e}")

        # 2. Working memory decay
        self.memory.working.decay_all(rate=0.02)
        stats["working_memory_slots"] = self.memory.working.size

        # 3. Local contradiction detection
        try:
            if self.memory.kg:
                contradictions = await self.memory.kg.find_contradictions()
                if contradictions:
                    stats["contradictions_found"] = len(contradictions)
                    self._pending_explorations.append({
                        "type": "contradiction_resolution",
                        "data": contradictions[:3],
                        "priority": 2,
                    })
        except Exception as e:
            logger.debug(f"Contradiction detection error: {e}")

        # 4. Random concept pair for novelty (free)
        try:
            if self.memory.kg:
                pair = await self.memory.kg.get_random_pair()
                if pair:
                    stats["concept_pair"] = pair
                    self._pending_explorations.append({
                        "type": "concept_blend",
                        "data": pair,
                        "priority": 1,
                    })
        except Exception:
            pass

        return stats

    async def _budget_operations(self) -> dict[str, Any]:
        """Operations that require LLM calls (budget-controlled)."""
        stats = {}

        if not self._pending_explorations:
            return stats

        # Sort by priority (higher first)
        self._pending_explorations.sort(key=lambda x: -x.get("priority", 0))

        # Process top exploration
        exploration = self._pending_explorations.pop(0)

        estimated_tokens = config.get("budget.curiosity_per_op_tokens", 500)
        allowed = await self.budget.request_curiosity_op(estimated_tokens)
        if not allowed:
            # Put it back for tomorrow
            self._pending_explorations.insert(0, exploration)
            stats["queued"] = len(self._pending_explorations)
            return stats

        try:
            if exploration["type"] == "concept_blend":
                result = await self._explore_concept_blend(exploration["data"])
                stats["blend_result"] = result
            elif exploration["type"] == "contradiction_resolution":
                result = await self._explore_contradiction(exploration["data"])
                stats["contradiction_result"] = result
        except Exception as e:
            logger.warning(f"Budget exploration error: {e}")

        self._exploration_log.append({
            "time": time.time(),
            "type": exploration["type"],
            "stats": stats,
        })
        return stats

    async def _explore_concept_blend(self, pair: tuple[str, str]) -> str:
        """Use LLM to explore blending two concepts."""
        prompt = (
            f"Consider these two concepts: '{pair[0]}' and '{pair[1]}'. "
            f"Is there an interesting connection or novel combination? "
            f"Respond briefly (2-3 sentences)."
        )
        result = await self.llm.complete(prompt, source="curiosity", task_type="simple_tasks")
        # Store insight
        if self.memory and len(result) > 20:
            await self.memory.store_knowledge(
                title=f"Blend: {pair[0]} + {pair[1]}",
                content=result,
                category="curiosity_blend",
            )
        return result

    async def _explore_contradiction(self, contradictions: list) -> str:
        """Use LLM to analyze contradictions."""
        desc = "; ".join(str(c) for c in contradictions[:3])
        prompt = (
            f"I found potential contradictions in my knowledge: {desc}. "
            f"Please analyze: are these real contradictions or just different perspectives? "
            f"Respond briefly."
        )
        return await self.llm.complete(prompt, source="curiosity", task_type="simple_tasks")

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "pending_explorations": len(self._pending_explorations),
            "explorations_done": len(self._exploration_log),
            "budget_remaining": self.budget.curiosity_ops_remaining,
        }
