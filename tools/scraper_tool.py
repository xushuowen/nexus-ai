"""Web scraping and content extraction tool using BeautifulSoup."""

from __future__ import annotations

import logging
import re
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class ScraperTool(BaseTool):
    name = "scraper"
    description = "Scrape a web page and extract structured content"
    category = "web"
    parameters = [
        ToolParameter("url", "string", "URL to scrape"),
        ToolParameter("selector", "string", "CSS selector to extract (optional)",
                       required=False, default=""),
        ToolParameter("extract_type", "string", "Type: 'text', 'links', 'images', 'tables'",
                       required=False, default="text", enum=["text", "links", "images", "tables"]),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        url = kwargs["url"]
        selector = kwargs.get("selector", "")
        extract_type = kwargs.get("extract_type", "text")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
        except ImportError:
            return ToolResult(success=False, output="", error="httpx not installed")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Fetch error: {e}")

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
        except ImportError:
            # Fallback: regex-based extraction
            return self._regex_extract(html, extract_type)

        if selector:
            elements = soup.select(selector)
            texts = [el.get_text(strip=True) for el in elements[:50]]
            return ToolResult(success=True, output="\n".join(texts))

        if extract_type == "links":
            links = []
            for a in soup.find_all("a", href=True)[:50]:
                links.append(f"[{a.get_text(strip=True)[:60]}]({a['href']})")
            return ToolResult(success=True, output="\n".join(links))

        elif extract_type == "images":
            images = []
            for img in soup.find_all("img", src=True)[:30]:
                alt = img.get("alt", "")
                images.append(f"![{alt}]({img['src']})")
            return ToolResult(success=True, output="\n".join(images))

        elif extract_type == "tables":
            tables = soup.find_all("table")[:5]
            output = []
            for i, table in enumerate(tables):
                rows = table.find_all("tr")
                for row in rows[:20]:
                    cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
                    output.append(" | ".join(cells))
                output.append("---")
            return ToolResult(success=True, output="\n".join(output))

        else:  # text
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            return ToolResult(success=True, output=text[:5000])

    def _regex_extract(self, html: str, extract_type: str) -> ToolResult:
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return ToolResult(success=True, output=text[:5000])
