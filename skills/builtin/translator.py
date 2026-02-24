"""Translation skill using LLM."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class TranslatorSkill(BaseSkill):
    name = "translator"
    description = "多語言翻譯（中英日韓等）"
    triggers = ["翻譯", "translate", "translation", "英翻中", "中翻英", "翻成",
                "英文怎麼說", "中文怎麼說", "日文怎麼說"]
    intent_patterns = [
        r"(翻成|改成|換成).{0,5}(中文|英文|日文|韓文|法文|德文|西班牙文|葡萄牙文)",
        r"(中文|英文|日文|韓文|法文).{0,5}(怎麼說|怎麼寫|是什麼|的說法|怎麼講)",
        r"用(英文|中文|日文|韓文)(說|寫|表達|怎麼講|怎麼說)",
        r"(這句|這段|以下|下面|上面|這些).{0,5}(的|請).{0,5}(翻譯|翻成|翻)",
        r"(幫我|請).{0,5}(翻譯|翻|翻成).{0,30}",
        r"(這個|這句|這段|這詞|這字).{0,5}(英文|中文|日文|怎麼翻|怎麼說)",
        r"(translate|翻譯).{0,15}(成|為|to|into|to English|to Chinese)",
        r"「.{1,80}」.{0,10}(英文|日文|中文|韓文|翻譯|怎麼說)",
        r"(how do you say|how to say).{0,30}in (Chinese|English|Japanese|Korean)",
        r"把.{1,50}(翻成|翻譯成|改成).{0,10}(中文|英文|日文|韓文)",
        r"(英文|中文|日文).{0,5}(翻譯|的意思|意思是|怎麼念)",
    ]
    category = "text"
    requires_llm = True

    instructions = "翻譯用戶提供的文字。自動偵測來源語言，翻成用戶要求的目標語言。"
    output_format = "原文: ...\n翻譯: ..."

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(content="⚠️ LLM 尚未初始化，無法執行翻譯。", success=False, source=self.name)

        # Detect target language from query for clearer instruction
        target_lang = self._detect_target_lang(query)
        lang_instruction = f"Translate to {target_lang}." if target_lang else \
            "If text is Chinese, translate to English. If English, translate to Chinese."

        prompt = (
            "You are a professional translator. "
            f"{lang_instruction} "
            "Only output the translation result, no explanations, no extra text.\n\n"
            f"Text to translate: {query}"
        )
        try:
            result = await llm.complete(prompt, task_type="simple_tasks", source="skill_translator")
            return SkillResult(content=result, success=True, source=self.name)
        except Exception as e:
            return SkillResult(content=f"翻譯失敗: {e}", success=False, source=self.name)

    def _detect_target_lang(self, query: str) -> str | None:
        """Detect requested target language from query."""
        lang_map = {
            "英文": "English", "英語": "English", "english": "English",
            "中文": "Traditional Chinese", "繁體中文": "Traditional Chinese",
            "簡體中文": "Simplified Chinese", "chinese": "Traditional Chinese",
            "日文": "Japanese", "日語": "Japanese", "japanese": "Japanese",
            "韓文": "Korean", "韓語": "Korean", "korean": "Korean",
            "法文": "French", "法語": "French", "french": "French",
            "德文": "German", "德語": "German", "german": "German",
            "西班牙文": "Spanish", "西班牙語": "Spanish", "spanish": "Spanish",
            "葡萄牙文": "Portuguese", "portuguese": "Portuguese",
        }
        query_lower = query.lower()
        # Check for "翻成X文" / "to X" patterns
        for kw, lang in lang_map.items():
            if kw in query_lower:
                return lang
        return None
