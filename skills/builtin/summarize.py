"""Summarize skill - condense text using LLM."""

from __future__ import annotations

from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class SummarizeSkill(BaseSkill):
    name = "summarize"
    description = "摘要長文本、文章或對話內容"
    triggers = ["摘要", "總結", "summarize", "summary", "簡述", "精簡", "重點"]
    category = "text"
    requires_llm = True

    instructions = "將用戶提供的文本精簡為重點摘要，保留關鍵資訊。"
    output_format = "## 摘要\n- 重點 1\n- 重點 2\n- 重點 3"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(content="LLM not available", success=False, source=self.name)

        prompt = (
            f"請將以下內容做精簡摘要，用繁體中文回覆，列出 3-5 個重點：\n\n{query}"
        )
        try:
            result = await llm.complete(prompt, task_type="simple_tasks", source="skill_summarize")
            return SkillResult(content=result, success=True, source=self.name)
        except Exception as e:
            return SkillResult(content=f"摘要失敗: {e}", success=False, source=self.name)
