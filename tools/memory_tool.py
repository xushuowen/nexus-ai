"""Memory management tool - OpenClaw-style memory_search / memory_get.
Exposes the 4-layer memory system as an LLM-callable tool."""

from __future__ import annotations

import json
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult


class MemorySearchTool(BaseTool):
    name = "memory_search"
    description = "Search across all memory layers (working, episodic, semantic, procedural)"
    category = "memory"
    parameters = [
        ToolParameter("query", "string", "Search query"),
        ToolParameter("top_k", "integer", "Number of results", required=False, default=5),
        ToolParameter("layer", "string", "Specific layer: 'all', 'working', 'episodic', 'fts', 'vector', 'graph'",
                       required=False, default="all",
                       enum=["all", "working", "episodic", "fts", "vector", "graph"]),
    ]

    def __init__(self) -> None:
        self._memory = None

    def set_memory(self, memory) -> None:
        self._memory = memory

    async def execute(self, **kwargs) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, output="", error="Memory system not connected")

        query = kwargs["query"]
        top_k = kwargs.get("top_k", 5)
        layer = kwargs.get("layer", "all")

        try:
            if layer == "all":
                results = await self._memory.search(query, top_k=top_k)
            elif layer == "working":
                raw = self._memory.working.search(query)
                results = [{"content": str(c), "source": "working", "score": a} for _, c, a in raw]
            elif layer == "episodic":
                eps = await self._memory.episodic.search(query, limit=top_k)
                results = [{"content": f"Q: {e.query}\nA: {e.response}", "source": "episodic", "score": e.confidence} for e in eps]
            elif layer == "fts":
                results = await self._memory.fts.search(query, limit=top_k)
            elif layer == "vector":
                results = await self._memory.vector.search(query, top_k=top_k)
            elif layer == "graph":
                results = await self._memory.kg.search(query, limit=top_k)
            else:
                results = await self._memory.search(query, top_k=top_k)

            if not results:
                return ToolResult(success=True, output="No results found.")

            output_lines = []
            for i, r in enumerate(results[:top_k], 1):
                content = r.get("content", str(r))[:300]
                source = r.get("source", "unknown")
                score = r.get("score", r.get("activation", ""))
                output_lines.append(f"[{i}] ({source}) {content}")
                if score:
                    output_lines[-1] += f" [score: {score}]"

            return ToolResult(success=True, output="\n\n".join(output_lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class MemoryStoreTool(BaseTool):
    name = "memory_store"
    description = "Store knowledge or facts into the memory system"
    category = "memory"
    parameters = [
        ToolParameter("content", "string", "Content to store"),
        ToolParameter("title", "string", "Title or label", required=False, default=""),
        ToolParameter("category", "string", "Category: 'fact', 'lesson', 'concept', 'procedure'",
                       required=False, default="fact"),
    ]

    def __init__(self) -> None:
        self._memory = None

    def set_memory(self, memory) -> None:
        self._memory = memory

    async def execute(self, **kwargs) -> ToolResult:
        if not self._memory:
            return ToolResult(success=False, output="", error="Memory system not connected")

        content = kwargs["content"]
        title = kwargs.get("title", content[:50])
        category = kwargs.get("category", "fact")

        try:
            await self._memory.store_knowledge(title=title, content=content, category=category)

            # Also add to knowledge graph if it looks like a concept
            if category == "concept":
                concept_id = title.lower().replace(" ", "_")[:30]
                await self._memory.kg.add_concept(concept_id, title, category="user_taught")

            return ToolResult(success=True, output=f"Stored: '{title}' [{category}]")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
