"""Web search skill using DuckDuckGo (free, no API key needed)."""

from __future__ import annotations

from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "網路搜尋 — 使用 DuckDuckGo（免費，不需要 API key）"
    triggers = ["搜尋", "search", "查一下", "google", "找一下", "look up"]
    category = "web"
    requires_llm = False

    instructions = "使用 DuckDuckGo HTML 搜尋，提取前幾筆結果。"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Strip trigger words
        for t in self.triggers:
            query = query.replace(t, "").strip()
        query = query.strip()

        if not query:
            return SkillResult(content="請提供搜尋關鍵字。", success=False, source=self.name)

        try:
            import httpx
            from nexus.security.url_filter import is_url_safe

            url = f"https://html.duckduckgo.com/html/?q={query}"
            safe, reason = is_url_safe(url)
            if not safe:
                return SkillResult(content=f"URL blocked: {reason}", success=False, source=self.name)

            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                html = resp.text

            # Parse results
            results = self._parse_results(html)
            if not results:
                return SkillResult(content=f"搜尋「{query}」沒有找到結果。", success=True, source=self.name)

            lines = [f"🔍 搜尋「{query}」的結果：\n"]
            for title, snippet in results[:5]:
                lines.append(f"**{title}**\n{snippet}\n")

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"搜尋失敗: {e}", success=False, source=self.name)

    def _parse_results(self, html: str) -> list[tuple[str, str]]:
        """Parse DuckDuckGo HTML results."""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.select(".result")[:5]:
                title_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                if title_el:
                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append((title, snippet))
        except ImportError:
            # Fallback: basic regex extraction
            import re
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</[^>]+>', html)
            for i, title in enumerate(titles[:5]):
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                results.append((title, snippet))
        return results
