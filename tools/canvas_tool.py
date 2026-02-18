"""Canvas visual workspace - renders HTML content to the Web UI via WebSocket."""

from __future__ import annotations

import json
import re

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult


class CanvasTool(BaseTool):
    name = "canvas"
    description = "Render HTML/Markdown content in a visual workspace panel"
    category = "visualization"
    parameters = [
        ToolParameter("content", "string", "HTML or Markdown content to render"),
        ToolParameter("content_type", "string", "Type: 'html', 'markdown', 'mermaid'",
                       required=False, default="html", enum=["html", "markdown", "mermaid"]),
        ToolParameter("title", "string", "Title for the canvas panel", required=False, default="Canvas"),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        content = kwargs["content"]
        content_type = kwargs.get("content_type", "html")
        title = kwargs.get("title", "Canvas")

        # Sanitize HTML content
        if content_type == "html":
            content = self._sanitize(content)

        output = {
            "type": "canvas",
            "content_type": content_type,
            "title": title,
            "content": content,
        }
        return ToolResult(success=True, output=json.dumps(output), data=output)

    def _sanitize(self, html: str) -> str:
        """Remove script tags and event handlers for safety."""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', html, flags=re.IGNORECASE)
        html = re.sub(r'href\s*=\s*["\']javascript:[^"\']*["\']', 'href="#"', html, flags=re.IGNORECASE)
        return html
