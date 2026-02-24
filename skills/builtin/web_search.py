"""Web search skill using DuckDuckGo (free, no API key needed)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class WebSearchSkill(BaseSkill):
    name = "web_search"
    description = "網路搜尋 — 使用 DuckDuckGo（免費，不需要 API key）"
    triggers = ["搜尋", "search", "查一下", "google", "找一下", "look up", "查詢", "幫我找", "網路查"]
    intent_patterns = [
        r"(我想知道|想了解|幫我查|想查).{2,30}",
        r"(有沒有|有關|關於).{2,20}(資料|資訊|消息|介紹)",
        r"(最新|現在).{0,5}(有什麼|發生了|怎麼了).{0,15}",
        r"(什麼是|誰是|哪裡有|怎麼).{2,25}",
        r"(幫我|請).{0,5}(找|查|搜).{2,20}",
    ]
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

            lines = [f"🔍 搜尋「{query}」找到 {len(results)} 筆結果：\n"]
            for i, (title, snippet, link) in enumerate(results[:5], 1):
                lines.append(f"**{i}. {title}**")
                if link:
                    lines.append(f"   🔗 {link}")
                if snippet:
                    lines.append(f"   {snippet}")
                lines.append("")

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"搜尋失敗: {e}", success=False, source=self.name)

    def _parse_results(self, html: str) -> list[tuple[str, str, str]]:
        """Parse DuckDuckGo HTML results. Returns (title, snippet, url)."""
        results = []
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for result in soup.select(".result")[:8]:
                title_el = result.select_one(".result__a")
                snippet_el = result.select_one(".result__snippet")
                url_el = result.select_one(".result__url")
                if title_el:
                    title = title_el.get_text(strip=True)
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    link = url_el.get_text(strip=True) if url_el else ""
                    if link and not link.startswith("http"):
                        link = "https://" + link
                    results.append((title, snippet, link))
        except ImportError:
            # Fallback: basic regex extraction
            titles = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</[^>]+>', html)
            urls = re.findall(r'class="result__url"[^>]*>(.*?)</[^>]+>', html)
            for i, title in enumerate(titles[:8]):
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else ""
                link = re.sub(r'<[^>]+>', '', urls[i]).strip() if i < len(urls) else ""
                if link and not link.startswith("http"):
                    link = "https://" + link
                results.append((title, snippet, link))
        return results
