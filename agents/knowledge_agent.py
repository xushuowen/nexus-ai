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

        KNOWLEDGE_SYSTEM = (
            "你是知識整合專家，同時有存取用戶的個人知識庫。\n"
            "回答時：\n"
            "1. 優先使用知識庫中的內容（標示來源）\n"
            "2. 分層次說明：核心概念 → 細節 → 實際應用\n"
            "3. 用具體例子說明抽象概念\n"
            "4. 點出知識之間的連結和脈絡\n"
            "5. 不確定的部分直接說不確定，不要猜測\n"
            "回應語言跟用戶相同。"
        )

        if results:
            mem_context = "\n\n".join(results)
            prompt = (
                f"從知識庫找到以下相關資料：\n\n{mem_context}\n\n"
                f"用戶問題：{message.content}\n\n"
                "請整合以上資料回答，若知識庫資料不足請說明。"
            )
            if self._llm:
                content = await self._llm.complete(
                    prompt, task_type="general", source="knowledge_agent",
                    system_prompt=KNOWLEDGE_SYSTEM,
                )
            else:
                content = "從記憶庫找到：\n\n" + "\n\n".join(results)
            confidence = 0.85
        elif self._llm:
            content = await self._llm.complete(
                message.content, task_type="general", source="knowledge_agent",
                system_prompt=KNOWLEDGE_SYSTEM,
            )
            confidence = 0.65
        else:
            content = "目前知識庫中沒有相關資料。"
            confidence = 0.2

        return AgentResult(content=content, confidence=confidence, source_agent=self.name)
