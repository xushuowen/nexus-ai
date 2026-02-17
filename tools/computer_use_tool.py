"""Computer Use tool - OpenClaw-style browser automation with screenshots.
Controls a dedicated browser instance for web tasks."""

from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class ComputerUseTool(BaseTool):
    name = "computer_use"
    description = "Control a browser: navigate, click, type, screenshot, extract content (OpenClaw-style)"
    category = "browser"
    parameters = [
        ToolParameter("action", "string",
                       "Action: navigate, click, type, screenshot, scroll, extract, back, wait",
                       enum=["navigate", "click", "type", "screenshot", "scroll", "extract", "back", "wait"]),
        ToolParameter("url", "string", "URL to navigate to (for 'navigate')", required=False),
        ToolParameter("selector", "string", "CSS selector for click/type target", required=False),
        ToolParameter("text", "string", "Text to type (for 'type' action)", required=False),
        ToolParameter("direction", "string", "Scroll direction: up/down", required=False, default="down"),
        ToolParameter("wait_ms", "integer", "Milliseconds to wait", required=False, default=1000),
    ]

    def __init__(self) -> None:
        self._browser = None
        self._page = None
        self._playwright = None
        self._available = False

    async def initialize(self) -> None:
        try:
            from playwright.async_api import async_playwright
            self._available = True
            logger.info("ComputerUse tool ready (Playwright available)")
        except ImportError:
            logger.info("ComputerUse: Playwright not installed, using httpx fallback")
            self._available = False

    async def _ensure_browser(self):
        """Lazy-launch browser on first use."""
        if self._page:
            return
        if not self._available:
            raise RuntimeError("Playwright not installed. Run: pip install playwright && playwright install chromium")
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=True)
        self._page = await self._browser.new_page(viewport={"width": 1280, "height": 720})

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "")

        if action == "navigate":
            return await self._navigate(kwargs.get("url", ""))
        elif action == "click":
            return await self._click(kwargs.get("selector", ""))
        elif action == "type":
            return await self._type_text(kwargs.get("selector", ""), kwargs.get("text", ""))
        elif action == "screenshot":
            return await self._screenshot()
        elif action == "scroll":
            return await self._scroll(kwargs.get("direction", "down"))
        elif action == "extract":
            return await self._extract(kwargs.get("selector", ""))
        elif action == "back":
            return await self._back()
        elif action == "wait":
            await asyncio.sleep(kwargs.get("wait_ms", 1000) / 1000)
            return ToolResult(success=True, output="Waited.")
        else:
            return ToolResult(success=False, output="", error=f"Unknown action: {action}")

    async def _navigate(self, url: str) -> ToolResult:
        if not url:
            return ToolResult(success=False, output="", error="URL required")
        if not self._available:
            return await self._httpx_fallback(url)
        try:
            await self._ensure_browser()
            await self._page.goto(url, timeout=15000, wait_until="domcontentloaded")
            title = await self._page.title()
            return ToolResult(success=True, output=f"Navigated to: {title}\nURL: {self._page.url}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _click(self, selector: str) -> ToolResult:
        if not selector:
            return ToolResult(success=False, output="", error="CSS selector required")
        try:
            await self._ensure_browser()
            await self._page.click(selector, timeout=5000)
            await self._page.wait_for_load_state("domcontentloaded")
            return ToolResult(success=True, output=f"Clicked: {selector}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Click failed: {e}")

    async def _type_text(self, selector: str, text: str) -> ToolResult:
        if not selector or not text:
            return ToolResult(success=False, output="", error="Selector and text required")
        try:
            await self._ensure_browser()
            await self._page.fill(selector, text, timeout=5000)
            return ToolResult(success=True, output=f"Typed into {selector}: {text[:50]}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Type failed: {e}")

    async def _screenshot(self) -> ToolResult:
        try:
            await self._ensure_browser()
            screenshot_bytes = await self._page.screenshot()
            b64 = base64.b64encode(screenshot_bytes).decode()
            return ToolResult(
                success=True,
                output=f"Screenshot captured ({len(screenshot_bytes)} bytes)",
                data={"image_base64": b64, "format": "png"},
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _scroll(self, direction: str) -> ToolResult:
        try:
            await self._ensure_browser()
            delta = -500 if direction == "up" else 500
            await self._page.mouse.wheel(0, delta)
            await asyncio.sleep(0.3)
            return ToolResult(success=True, output=f"Scrolled {direction}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _extract(self, selector: str) -> ToolResult:
        try:
            await self._ensure_browser()
            if selector:
                elements = await self._page.query_selector_all(selector)
                texts = []
                for el in elements[:50]:
                    text = await el.inner_text()
                    texts.append(text.strip())
                return ToolResult(success=True, output="\n".join(texts))
            else:
                text = await self._page.inner_text("body")
                return ToolResult(success=True, output=text[:5000])
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _back(self) -> ToolResult:
        try:
            await self._ensure_browser()
            await self._page.go_back()
            title = await self._page.title()
            return ToolResult(success=True, output=f"Back to: {title}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _httpx_fallback(self, url: str) -> ToolResult:
        """Fallback when Playwright not available."""
        try:
            import httpx
            import re
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                text = resp.text
                # Extract title
                title_match = re.search(r'<title[^>]*>(.*?)</title>', text, re.DOTALL | re.IGNORECASE)
                title = title_match.group(1).strip() if title_match else url
                # Clean HTML
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return ToolResult(success=True, output=f"Title: {title}\n\n{text[:4000]}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def shutdown(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
