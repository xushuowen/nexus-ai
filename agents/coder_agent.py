"""Code generation and debugging specialist agent."""

from __future__ import annotations

import re
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

CODER_SYSTEM = """You are an expert programmer. Write clean, efficient, well-documented code.
- Follow best practices for the requested language
- Include error handling where appropriate
- Provide brief explanations of your approach
- If debugging, identify the root cause and fix"""


class CoderAgent(BaseAgent):
    name = "coder"
    description = "Code generation, debugging, and programming assistance"
    capabilities = [AgentCapability.CODE]
    priority = 8

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    async def initialize(self) -> None:
        await super().initialize()

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        code_keywords = [
            "code", "function", "class", "implement", "debug", "fix", "error",
            "python", "javascript", "typescript", "rust", "java", "html", "css",
            "write a", "create a", "program", "script", "api", "algorithm",
            "bug", "syntax", "compile", "refactor",
        ]
        score = sum(0.15 for kw in code_keywords if kw in text)
        # Boost if code block present
        if "```" in message.content:
            score += 0.3
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        if not self._llm:
            return AgentResult(
                content="Coder agent not connected to LLM provider.",
                confidence=0.0,
                source_agent=self.name,
            )

        memory_ctx = context.get("memory", "")
        prompt = message.content
        if memory_ctx:
            prompt = f"Relevant context:\n{memory_ctx}\n\nUser request:\n{message.content}"

        response = await self._llm.complete(
            prompt,
            task_type="code_generation",
            source="coder_agent",
            system_prompt=CODER_SYSTEM,
        )

        # Estimate confidence based on whether code was actually generated
        has_code = "```" in response or "def " in response or "function " in response
        confidence = 0.85 if has_code else 0.6

        return AgentResult(
            content=response,
            confidence=confidence,
            source_agent=self.name,
            reasoning_trace=["Analyzed code request", "Generated code solution"],
        )
