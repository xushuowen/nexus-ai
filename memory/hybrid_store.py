"""Unified 4-layer memory interface combining all memory subsystems."""

from __future__ import annotations

import logging
from typing import Any

from nexus.memory.working_memory import WorkingMemory
from nexus.memory.episodic_memory import EpisodicMemory
from nexus.memory.fts_store import FTSStore
from nexus.memory.vector_store import VectorStore
from nexus.memory.knowledge_graph import KnowledgeGraph
from nexus.memory.procedural_memory import ProceduralMemory
from nexus.memory.temporal import TemporalRetriever
from nexus.memory.session import SessionManager
from nexus.memory.experience_memory import ExperienceMemory

logger = logging.getLogger(__name__)


class HybridMemory:
    """Unified interface to the 4-layer adaptive neural memory system.

    Layer 1: Working Memory (local, 0 tokens)
    Layer 2: Episodic Memory (SQLite, low tokens for lesson extraction)
    Layer 3: Semantic Memory (FTS5 + ChromaDB + Knowledge Graph, 0 tokens)
    Layer 4: Procedural Memory (cached reasoning chains, 0 tokens)
    """

    def __init__(self) -> None:
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.fts = FTSStore()
        self.vector = VectorStore()
        self.kg = KnowledgeGraph()
        self.procedural = ProceduralMemory()
        self.temporal = TemporalRetriever()
        self.session = SessionManager()
        self.experience = ExperienceMemory()

    async def initialize(self) -> None:
        """Initialize all memory layers."""
        await self.episodic.initialize()
        await self.fts.initialize()
        await self.vector.initialize()
        await self.kg.initialize()
        await self.procedural.initialize()
        await self.session.initialize()
        await self.experience.initialize()
        logger.info("All memory layers initialized")

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Search across all memory layers and merge results."""
        results = []

        # Layer 1: Working memory (instant)
        wm_results = self.working.search(query)
        for key, content, attention in wm_results:
            results.append({
                "content": str(content),
                "source": "working_memory",
                "score": attention,
                "timestamp": 0,
            })

        # Layer 2: Episodic memory
        try:
            episodes = await self.episodic.search(query, limit=top_k)
            for ep in episodes:
                results.append({
                    "content": f"Q: {ep.query}\nA: {ep.response}",
                    "source": "episodic",
                    "score": ep.confidence,
                    "timestamp": ep.timestamp,
                })
        except Exception as e:
            logger.warning(f"Episodic search error: {e}")

        # Layer 3a: FTS keyword search
        try:
            fts_results = await self.fts.search(query, limit=top_k)
            for item in fts_results:
                results.append({
                    "content": item.get("content", ""),
                    "source": "fts",
                    "score": item.get("score", 0.5),
                    "timestamp": item.get("timestamp", 0),
                })
        except Exception as e:
            logger.warning(f"FTS search error: {e}")

        # Layer 3b: Vector similarity search
        try:
            vec_results = await self.vector.search(query, top_k=top_k)
            for item in vec_results:
                results.append({
                    "content": item.get("content", ""),
                    "source": "vector",
                    "score": 1.0 - item.get("distance", 0.5),
                    "timestamp": item.get("metadata", {}).get("timestamp", 0),
                })
        except Exception as e:
            logger.warning(f"Vector search error: {e}")

        # Layer 3c: Knowledge graph
        try:
            kg_results = await self.kg.search(query, limit=top_k)
            for item in kg_results:
                content_parts = [f"Concept: {item['label']}"]
                if item.get("connections"):
                    content_parts.append(f"Related: {', '.join(item['connections'][:5])}")
                results.append({
                    "content": " | ".join(content_parts),
                    "source": "knowledge_graph",
                    "score": item.get("activation", 0.5),
                    "timestamp": 0,
                })
        except Exception as e:
            logger.warning(f"KG search error: {e}")

        # Apply temporal ranking
        results = self.temporal.rank_results(results)

        # Deduplicate and return top results
        seen = set()
        unique = []
        for r in results:
            key = r["content"][:100]
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique[:top_k]

    async def get_procedural(self, query: str) -> str | None:
        """Check procedural memory cache. Returns cached response or None."""
        return await self.procedural.lookup(query)

    async def store_procedural(self, query: str, response: str) -> None:
        """Cache a successful response in procedural memory."""
        await self.procedural.store(query, response)

    async def store_interaction(self, query: str, response: str, metadata: dict | None = None) -> None:
        """Store an interaction across relevant memory layers."""
        # Working memory
        self.working.store(f"last_query", query)
        self.working.store(f"last_response", response[:500])

        # Episodic memory
        await self.episodic.store(query, response, metadata=metadata)

        # FTS (for keyword search)
        await self.fts.store(
            title=query[:100],
            content=response,
            category="interaction",
            source="conversation",
        )

        # Vector store (for semantic search)
        await self.vector.store(
            f"Q: {query}\nA: {response[:500]}",
            metadata={"type": "interaction"},
        )

    async def store_knowledge(self, title: str, content: str, category: str = "") -> None:
        """Store a piece of knowledge in semantic memory layers."""
        await self.fts.store(title=title, content=content, category=category)
        await self.vector.store(content, metadata={"title": title, "category": category})

    async def forget(self, query: str, limit: int = 20) -> int:
        """Delete FTS entries matching query. Returns number of items deleted."""
        deleted = 0
        try:
            results = await self.fts.search(query, limit=limit)
            for item in results:
                rowid = item.get("id")
                if rowid is not None:
                    await self.fts.delete(rowid)
                    deleted += 1
            if deleted:
                logger.info("Memory forget: removed %d FTS entries matching '%s'", deleted, query)
        except Exception as e:
            logger.warning("Memory forget error: %s", e)
        return deleted

    async def close(self) -> None:
        """Close all memory connections."""
        await self.episodic.close()
        await self.fts.close()
        await self.vector.close()
        await self.kg.close()
        await self.procedural.close()
        await self.experience.close()
        await self.session.close()
