"""Text tools skill - word count, encoding, formatting utilities."""

from __future__ import annotations

import base64
import json
import re
import unicodedata
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class TextToolsSkill(BaseSkill):
    name = "text_tools"
    description = "文字工具 — 字數統計、Base64、JSON 格式化等"
    triggers = ["字數", "word count", "base64", "json格式", "text tool", "字元",
                "統計", "encode", "decode", "格式化", "format json"]
    intent_patterns = [
        r"(這段文字|這篇|以下|這些).{0,10}(有幾個|有多少)(字|字元|單字|字數)",
        r"幫我.{0,5}(數|統計|計算).{0,10}(字數|字元|字)",
        r"(base64|Base64).{0,10}(編碼|解碼|轉換|encode|decode)",
        r"(json|JSON).{0,10}(格式化|排版|美化|格式|整理)",
        r"(這段|這個).{0,10}(有幾字|字數是|共幾個字)",
    ]
    category = "utility"
    requires_llm = False

    instructions = (
        "文字工具：\n"
        "1. 字數統計：「字數 要統計的文字」\n"
        "2. Base64 編碼：「base64 encode 文字」\n"
        "3. Base64 解碼：「base64 decode 編碼」\n"
        "4. JSON 格式化：「json格式 {json字串}」"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text_lower = query.lower()

        if "base64" in text_lower:
            return self._base64(query)
        elif "json" in text_lower and any(k in text_lower for k in ["格式", "format", "美化", "排版", "整理"]):
            # Require "json" to be present to avoid triggering on generic "格式化"
            return self._format_json(query)
        elif any(k in text_lower for k in ["json格式", "format json", "json format"]):
            return self._format_json(query)
        else:
            return self._word_count(query)

    def _word_count(self, text: str) -> SkillResult:
        # Remove trigger words
        for t in self.triggers:
            text = text.replace(t, "")
        text = text.strip()

        if not text:
            return SkillResult(content="請提供要統計的文字。", success=False, source=self.name)

        total_chars = len(text)
        chars_no_space = len(text.replace(" ", "").replace("\n", ""))

        # Count CJK characters
        cjk_count = sum(1 for c in text if unicodedata.category(c).startswith(('Lo',)))
        # Count English words
        english_words = len(re.findall(r'[a-zA-Z]+', text))
        # Count lines
        lines = text.count('\n') + 1
        # Count sentences (rough)
        sentences = len(re.split(r'[。.!！?？]+', text)) - 1

        result = (
            f"📊 **文字統計**\n\n"
            f"📝 總字元: {total_chars}\n"
            f"🔤 不含空白: {chars_no_space}\n"
            f"🀄 中文字: {cjk_count}\n"
            f"🔠 英文單字: {english_words}\n"
            f"📄 行數: {lines}\n"
            f"📎 句子數: {max(1, sentences)}"
        )
        return SkillResult(content=result, success=True, source=self.name)

    def _base64(self, query: str) -> SkillResult:
        text_lower = query.lower()

        if "decode" in text_lower or "解碼" in text_lower:
            # Decode
            data = re.sub(r'(base64|decode|解碼)', '', query, flags=re.IGNORECASE).strip()
            if not data:
                return SkillResult(content="請提供要解碼的 Base64 字串。", success=False, source=self.name)
            try:
                decoded = base64.b64decode(data).decode("utf-8")
                return SkillResult(content=f"🔓 Base64 解碼結果:\n```\n{decoded}\n```", success=True, source=self.name)
            except Exception as e:
                return SkillResult(content=f"解碼失敗: {e}", success=False, source=self.name)
        else:
            # Encode
            data = re.sub(r'(base64|encode|編碼)', '', query, flags=re.IGNORECASE).strip()
            if not data:
                return SkillResult(content="請提供要編碼的文字。", success=False, source=self.name)
            encoded = base64.b64encode(data.encode("utf-8")).decode("ascii")
            return SkillResult(content=f"🔐 Base64 編碼結果:\n```\n{encoded}\n```", success=True, source=self.name)

    def _format_json(self, query: str) -> SkillResult:
        # Extract JSON from query
        for t in ["json格式", "format json", "json format", "格式化"]:
            query = query.replace(t, "").strip()

        if not query:
            return SkillResult(content="請提供要格式化的 JSON。", success=False, source=self.name)

        try:
            parsed = json.loads(query)
            formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
            return SkillResult(
                content=f"✨ 格式化 JSON:\n```json\n{formatted}\n```",
                success=True, source=self.name,
            )
        except json.JSONDecodeError as e:
            return SkillResult(content=f"JSON 解析失敗: {e}", success=False, source=self.name)
