"""Translation skill using LLM."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class TranslatorSkill(BaseSkill):
    name = "translator"
    description = "多語言翻譯（中英日韓等）"
    triggers = ["翻譯", "translate", "translation", "英文", "中文", "日文", "韓文",
                "英翻中", "中翻英", "翻成"]
    intent_patterns = [
        r"(翻成|改成|換成|用).{0,5}(中文|英文|日文|韓文|法文|德文|西班牙文)",
        r"(中文|英文|日文|韓文).{0,5}(怎麼說|怎麼寫|是什麼|的說法|怎麼講)",
        r"用英文(說|寫|表達|怎麼講|怎麼說)",
        r"(這句|這段|以下).{0,5}(的|請).{0,5}(翻譯|翻成)",
        r"(幫我|請).{0,5}(翻譯|翻|翻成).{0,20}",
        r"(這個|這句|這段).{0,5}(英文|中文|日文|怎麼翻)",
        r"(translate|翻譯).{0,15}(成|為|to|into)",
        r"「.{1,50}」.{0,5}(英文怎麼說|日文怎麼說|中文怎麼說)",
    ]
    category = "text"
    requires_llm = True

    instructions = "翻譯用戶提供的文字。自動偵測來源語言，翻成用戶要求的目標語言。"
    output_format = "原文: ...\n翻譯: ..."

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(content="LLM not available", success=False, source=self.name)

        prompt = (
            "You are a professional translator. "
            "Detect the source language and translate to the language the user requests. "
            "If no target language is specified, translate Chinese↔English (swap). "
            "Only output the translation, no explanations.\n\n"
            f"User request: {query}"
        )
        try:
            result = await llm.complete(prompt, task_type="simple_tasks", source="skill_translator")
            return SkillResult(content=result, success=True, source=self.name)
        except Exception as e:
            return SkillResult(content=f"翻譯失敗: {e}", success=False, source=self.name)
