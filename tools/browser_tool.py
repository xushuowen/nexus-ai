"""Web browsing tool using Playwright CDP (headless mode)."""

from __future__ import annotations

import logging
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class BrowserTool(BaseTool):
    name = "browser"
    description = "Browse a web page and extract its content"
    category = "web"
    parameters = [
        ToolParameter("url", "string", "The URL to browse"),
        ToolParameter("extract", "string", "What to extract: 'text', 'links', 'all'",
                       required=False, default="text"),
    ]

    def __init__(self) -> None:
        self._available = False

    async def initialize(self) -> None:
        try:
            import playwright  # noqa: F401
            self._available = True
        except ImportError:
            logger.info("Playwright not installed. Browser tool using httpx fallback.")

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs.get("url", "")
        extract = kwargs.get("extract", "text")

        if not url:
            return ToolResult(success=False, output="", error="URL is required")

        if self._available:
            return await self._playwright_fetch(url, extract)
        return await self._httpx_fetch(url, extract)

    async def _playwright_fetch(self, url: str, extract: str) -> ToolResult:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=15000)
                if extract == "links":
                    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => ({text: e.textContent, href: e.href}))")
                    await browser.close()
                    content = "\n".join(f"- [{l['text'].strip()}]({l['href']})" for l in links[:50])
                    return ToolResult(success=True, output=content)
                else:
                    text = await page.inner_text("body")
                    await browser.close()
                    return ToolResult(success=True, output=text[:5000])
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _httpx_fetch(self, url: str, extract: str) -> ToolResult:
        try:
            import httpx
            import re
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return ToolResult(success=True, output=text[:5000])
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
