"""Research and web search specialist agent — fetches real data before synthesizing."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent

RESEARCH_SYSTEM = """你是深度研究專家，擅長整合即時資訊與背景知識。回答研究型問題時：
1. 先給結論，再給支持依據（結論前置）
2. 如果有即時搜尋資料，優先引用，並標示「來源：...」
3. 區分「確定的事實」vs「推測/觀點」，不確定時直接說明
4. 若有多個觀點，列出各方說法再做綜合分析
5. 回答結尾提供 1-2 個延伸追問建議
回應語言跟用戶相同。"""


class ResearchAgent(BaseAgent):
    name = "research"
    description = "Research, web search, information synthesis"
    capabilities = [AgentCapability.RESEARCH, AgentCapability.WEB]
    priority = 7

    def __init__(self) -> None:
        super().__init__()
        self._llm = None
        self._skill_loader = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def set_skill_loader(self, skill_loader) -> None:
        self._skill_loader = skill_loader

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

        # ── Step 1: real-time web search ──────────────────────────────
        web_results = await self._web_search(message.content, context)

        # ── Step 2: synthesize with LLM ───────────────────────────────
        parts: list[str] = []
        trace: list[str] = []

        if web_results:
            parts.append(f"【即時搜尋結果】\n{web_results}")
            trace.append("Web search: results fetched")
        else:
            trace.append("Web search: skipped or no results")

        if context.get("memory"):
            parts.append(f"【記憶庫資料】\n{context['memory']}")
            trace.append("Memory context injected")

        parts.append(f"【用戶問題】\n{message.content}")

        if web_results:
            parts.append("請基於以上即時搜尋結果和記憶庫資料來回答問題。有資料來源時請在答案中標示。")

        prompt = "\n\n".join(parts)
        response = await self._llm.complete(
            prompt,
            task_type="complex_reasoning",
            source="research_agent",
            system_prompt=RESEARCH_SYSTEM,
        )
        trace.append("LLM synthesis complete")

        confidence = 0.85 if web_results else 0.65
        return AgentResult(
            content=response,
            confidence=confidence,
            source_agent=self.name,
            reasoning_trace=trace,
        )

    async def _web_search(self, query: str, context: dict[str, Any]) -> str:
        """Run web_search skill; returns raw text or empty string on failure."""
        if not self._skill_loader:
            return ""
        search_skill = next(
            (s for s in self._skill_loader.list_skills() if s.name == "web_search"),
            None,
        )
        if not search_skill:
            return ""
        try:
            # Use first 200 chars as search query (handles long research questions)
            search_q = query.strip()[:200]
            result = await search_skill.execute(search_q, context)
            return result.content if result.success and result.content else ""
        except Exception:
            return ""
