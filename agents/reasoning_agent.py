"""Chain-of-thought reasoning specialist agent."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

COT_SYSTEM = """You are a logical reasoning specialist. Break down complex problems step by step.
Use chain-of-thought reasoning:
1. Identify the core question
2. List relevant facts and assumptions
3. Reason through each step explicitly
4. State your conclusion with confidence level
Be precise and show your work."""


class ReasoningAgent(BaseAgent):
    name = "reasoning"
    description = "Chain-of-thought reasoning for complex logical problems"
    capabilities = [AgentCapability.REASONING]
    priority = 7

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = [
            "why", "how", "reason", "logic", "analyze", "think", "solve",
            "prove", "calculate", "if then", "therefore", "because",
            "step by step", "break down", "figure out",
        ]
        score = sum(0.12 for kw in keywords if kw in text)
        if context.get("complexity") == "complex":
            score += 0.2
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        if not self._llm:
            return AgentResult(content="Reasoning agent not connected.", confidence=0.0, source_agent=self.name)

        memory_ctx = context.get("memory", "")
        prompt = message.content
        if memory_ctx:
            prompt = f"Context:\n{memory_ctx}\n\nProblem:\n{message.content}"

        response = await self._llm.complete(
            prompt, task_type="complex_reasoning", source="reasoning_agent",
            system_prompt=COT_SYSTEM,
        )

        # Parse confidence from response if present
        confidence = 0.75
        if "high confidence" in response.lower():
            confidence = 0.9
        elif "uncertain" in response.lower() or "not sure" in response.lower():
            confidence = 0.5

        return AgentResult(
            content=response, confidence=confidence, source_agent=self.name,
            reasoning_trace=["Applied chain-of-thought reasoning"],
        )
