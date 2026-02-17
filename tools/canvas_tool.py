"""Agent-driven visual workspace - renders HTML content to the UI."""

from __future__ import annotations

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

        # Wrap content for the frontend to render
        output = {
            "type": "canvas",
            "content_type": content_type,
            "title": title,
            "content": content,
        }
        import json
        return ToolResult(
            success=True,
            output=json.dumps(output),
            data=output,
        )
