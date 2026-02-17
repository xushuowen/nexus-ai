"""Research and web search specialist agent."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

RESEARCH_SYSTEM = """You are a research specialist. Help users find and synthesize information.
- Provide well-structured, factual answers
- Cite sources when possible
- Distinguish between facts and opinions
- Acknowledge uncertainty when appropriate"""


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Research, information synthesis, and web search"
    capabilities = [AgentCapability.RESEARCH, AgentCapability.WEB]
    priority = 7

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = [
            "search", "find", "research", "latest", "news", "what is",
            "who is", "when did", "where is", "how many", "statistics",
            "compare", "difference between", "history of", "explain",
        ]
        score = sum(0.15 for kw in keywords if kw in text)
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        if not self._llm:
            return AgentResult(content="Research agent not connected.", confidence=0.0, source_agent=self.name)

        memory_ctx = context.get("memory", "")
        prompt = message.content
        if memory_ctx:
            prompt = f"Previous knowledge:\n{memory_ctx}\n\nResearch query:\n{message.content}"

        response = await self._llm.complete(
            prompt, task_type="complex_reasoning", source="research_agent",
            system_prompt=RESEARCH_SYSTEM,
        )

        return AgentResult(content=response, confidence=0.75, source_agent=self.name,
                           reasoning_trace=["Analyzed research query", "Synthesized information"])
