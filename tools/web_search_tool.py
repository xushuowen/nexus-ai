"""Web search tool - search the internet and return results.
Uses DuckDuckGo (free, no API key needed) as primary search engine."""

from __future__ import annotations

import logging
import re
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web and return relevant results (DuckDuckGo, free)"
    category = "web"
    parameters = [
        ToolParameter("query", "string", "Search query"),
        ToolParameter("max_results", "integer", "Maximum results to return", required=False, default=5),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        query = kwargs["query"]
        max_results = kwargs.get("max_results", 5)

        # Try duckduckgo_search first (best free option)
        try:
            return await self._ddg_search(query, max_results)
        except ImportError:
            pass

        # Fallback: scrape DuckDuckGo HTML
        return await self._ddg_html_search(query, max_results)

    async def _ddg_search(self, query: str, max_results: int) -> ToolResult:
        """Search using duckduckgo_search library."""
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"**{r['title']}**\n{r['href']}\n{r['body']}")
        if not results:
            return ToolResult(success=True, output="No results found.")
        return ToolResult(success=True, output="\n\n---\n\n".join(results))

    async def _ddg_html_search(self, query: str, max_results: int) -> ToolResult:
        """Fallback: scrape DuckDuckGo HTML results."""
        try:
            import httpx
            url = "https://html.duckduckgo.com/html/"
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.post(url, data={"q": query})
                resp.raise_for_status()
                html = resp.text

            # Parse results with regex
            results = []
            # Find result snippets
            pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, html, re.DOTALL)
            for href, title, snippet in matches[:max_results]:
                title_clean = re.sub(r'<[^>]+>', '', title).strip()
                snippet_clean = re.sub(r'<[^>]+>', '', snippet).strip()
                results.append(f"**{title_clean}**\n{href}\n{snippet_clean}")

            if not results:
                return ToolResult(success=True, output="No results found. Try a different query.")
            return ToolResult(success=True, output="\n\n---\n\n".join(results))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Search failed: {e}")
