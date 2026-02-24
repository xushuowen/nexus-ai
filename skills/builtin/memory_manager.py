"""Memory Manager Skill — 讓使用者查詢、忘記長期記憶中的內容。"""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class MemoryManagerSkill(BaseSkill):
    name = "memory_manager"
    description = "記憶管理 — 搜尋或刪除 Nexus 長期記憶中的特定內容"
    triggers = [
        "忘記", "遺忘", "刪除記憶", "清除記憶", "forget",
        "查記憶", "記憶搜尋", "記憶裡", "memory search",
    ]
    intent_patterns = [
        r"(幫我|請)?忘記.{1,40}",
        r"(幫我|請)?刪除.{0,10}記憶.{0,20}",
        r"(查|搜尋|找).{0,5}記憶",
        r"記憶(裡|中).{0,20}(有什麼|有沒有|找|搜)",
        r"forget\s+.{1,60}",
        r"memory\s+(search|delete|forget)",
    ]
    category = "memory"
    requires_llm = False

    instructions = (
        "記憶管理指令：\n"
        "• 搜尋：「查記憶 Python」「記憶裡有什麼關於 AI 的？」\n"
        "• 刪除：「忘記 Python」「刪除記憶 舊計劃」\n"
        "• 清空工作記憶：「清除工作記憶」"
    )

    def __init__(self) -> None:
        self._memory: Any = None

    def set_memory(self, memory: Any) -> None:
        self._memory = memory

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Inject memory from context if not already set
        if self._memory is None:
            self._memory = context.get("memory_obj")

        if self._memory is None:
            return SkillResult(
                content="⚠️ 記憶系統尚未初始化，請稍後再試。",
                success=False, source=self.name,
            )

        text = query.strip()
        text_lower = text.lower()

        # ── Clear working memory ─────────────────────────────────────────────
        if any(k in text_lower for k in ["清除工作記憶", "clear working", "清空工作"]):
            self._memory.working.clear()
            return SkillResult(
                content="🧹 工作記憶已清空。",
                success=True, source=self.name,
            )

        # ── Forget / delete ──────────────────────────────────────────────────
        is_forget = any(k in text_lower for k in ["忘記", "遺忘", "刪除記憶", "清除記憶", "forget", "delete"])
        if is_forget:
            search_term = self._extract_subject(text, ["忘記", "遺忘", "刪除記憶", "清除記憶", "forget", "delete"])
            if not search_term:
                return SkillResult(
                    content="請告訴我要忘記什麼，例如：「忘記 Python 筆記」",
                    success=False, source=self.name,
                )
            deleted = await self._memory.forget(search_term)
            if deleted:
                return SkillResult(
                    content=f"🗑️ 已從長期記憶中刪除 **{deleted}** 筆關於「{search_term}」的內容。",
                    success=True, source=self.name,
                )
            else:
                return SkillResult(
                    content=f"🔍 沒有找到關於「{search_term}」的記憶，無需刪除。",
                    success=True, source=self.name,
                )

        # ── Search / query ───────────────────────────────────────────────────
        search_term = self._extract_subject(text, ["查記憶", "記憶搜尋", "記憶裡", "memory search", "查", "搜尋", "找"])
        if not search_term:
            search_term = text

        results = await self._memory.search(search_term, top_k=5)
        if not results:
            return SkillResult(
                content=f"🔍 記憶中沒有找到關於「{search_term}」的內容。",
                success=True, source=self.name,
            )

        lines = [f"🧠 **記憶搜尋結果**（關鍵字：{search_term}）\n"]
        for i, r in enumerate(results, 1):
            source = r.get("source", "?")
            content = r.get("content", "")[:200]
            lines.append(f"**[{i}]** `{source}`\n{content}\n")

        return SkillResult(
            content="\n".join(lines),
            success=True, source=self.name,
        )

    @staticmethod
    def _extract_subject(text: str, prefixes: list[str]) -> str:
        """Remove leading command words and return the subject."""
        result = text
        for prefix in sorted(prefixes, key=len, reverse=True):
            pattern = re.compile(re.escape(prefix) + r'\s*', re.IGNORECASE)
            result = pattern.sub("", result, count=1).strip()
        return result
