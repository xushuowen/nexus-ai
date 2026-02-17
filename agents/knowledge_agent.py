"""Knowledge graph query specialist agent."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent


class KnowledgeAgent(BaseAgent):
    name = "knowledge"
    description = "Knowledge graph queries, concept exploration, and relationship mapping"
    capabilities = [AgentCapability.KNOWLEDGE]
    priority = 6

    def __init__(self) -> None:
        super().__init__()
        self._memory = None
        self._llm = None

    def set_dependencies(self, memory, llm) -> None:
        self._memory = memory
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["relationship", "connected", "related", "graph", "concept", "knowledge",
                     "remember", "recall", "you told me", "i told you", "do you know"]
        score = sum(0.15 for kw in keywords if kw in text)
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        results = []

        if self._memory:
            # Search across memory layers
            mem_results = await self._memory.search(message.content, top_k=5)
            if mem_results:
                for r in mem_results:
                    results.append(f"[{r['source']}] {r['content'][:200]}")

        if results:
            content = "Here's what I found in my knowledge:\n\n" + "\n\n".join(results)
            confidence = 0.8
        elif self._llm:
            content = await self._llm.complete(
                message.content, task_type="general", source="knowledge_agent",
                system_prompt="Answer based on your training knowledge. Be concise.",
            )
            confidence = 0.6
        else:
            content = "I don't have any stored knowledge about this yet."
            confidence = 0.2

        return AgentResult(content=content, confidence=confidence, source_agent=self.name)
