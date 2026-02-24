"""Summarize skill - condense text using LLM."""

from __future__ import annotations

from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class SummarizeSkill(BaseSkill):
    name = "summarize"
    description = "摘要長文本、文章或對話內容"
    triggers = ["摘要", "總結", "summarize", "summary", "簡述", "精簡", "重點"]
    intent_patterns = [
        r"(整理|歸納|概括).{0,15}(一下|這|它|這篇|這段)",
        r"(這|這篇|這段|這個).{0,10}(說|講|寫).{0,10}(什麼|重點|大意)",
        r"幫我.{0,5}(整理|總結|摘要|抓重點|歸納)",
        r"(長話短說|簡單來說|用幾句話|簡短說明)",
        r"(這篇文章|這段文字|這個內容).{0,10}(講什麼|說什麼|重點是)",
        r"(摘要|重點|大意|結論|要點).{0,5}(是什麼|有哪些|幫我整理)",
        r"(太長了|內容太多).{0,10}(幫我|請).{0,5}(整理|濃縮|簡化)",
    ]
    category = "text"
    requires_llm = True

    instructions = "將用戶提供的文本精簡為重點摘要，保留關鍵資訊。"
    output_format = "## 摘要\n- 重點 1\n- 重點 2\n- 重點 3"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(content="⚠️ LLM 尚未初始化，無法執行摘要。", success=False, source=self.name)

        prompt = (
            f"請將以下內容做精簡摘要，用繁體中文回覆，列出 3-5 個重點：\n\n{query}"
        )
        try:
            result = await llm.complete(prompt, task_type="simple_tasks", source="skill_summarize")
            return SkillResult(content=result, success=True, source=self.name)
        except Exception as e:
            return SkillResult(content=f"摘要失敗: {e}", success=False, source=self.name)
