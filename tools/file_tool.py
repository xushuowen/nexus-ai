"""File read/write/search operations tool (protected by filesystem_scope)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config


class FileReadTool(BaseTool):
    name = "file_read"
    description = "Read the contents of a file"
    category = "file"
    parameters = [
        ToolParameter("path", "string", "File path to read"),
        ToolParameter("max_lines", "integer", "Maximum lines to read", required=False, default=200),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        max_lines = kwargs.get("max_lines", 200)
        if not self._is_allowed(path):
            return ToolResult(success=False, output="", error="Path not in allowed scope")
        try:
            p = Path(path)
            if not p.exists():
                return ToolResult(success=False, output="", error="File not found")
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _is_allowed(self, path: str) -> bool:
        allowed = config.get("security.allowed_paths", ["./data", "./workspace"])
        abs_path = str(Path(path).resolve())
        return any(abs_path.startswith(str(Path(a).resolve())) for a in allowed)


class FileWriteTool(BaseTool):
    name = "file_write"
    description = "Write content to a file"
    category = "file"
    requires_confirmation = True
    parameters = [
        ToolParameter("path", "string", "File path to write"),
        ToolParameter("content", "string", "Content to write"),
        ToolParameter("append", "boolean", "Append instead of overwrite", required=False, default=False),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        append = kwargs.get("append", False)
        if not self._is_allowed(path):
            return ToolResult(success=False, output="", error="Path not in allowed scope")
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            p.write_text(content, encoding="utf-8") if not append else p.open(mode, encoding="utf-8").write(content)
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _is_allowed(self, path: str) -> bool:
        allowed = config.get("security.allowed_paths", ["./data", "./workspace"])
        abs_path = str(Path(path).resolve())
        return any(abs_path.startswith(str(Path(a).resolve())) for a in allowed)


class FileSearchTool(BaseTool):
    name = "file_search"
    description = "Search for files by name pattern"
    category = "file"
    parameters = [
        ToolParameter("pattern", "string", "Glob pattern to search (e.g., '*.py')"),
        ToolParameter("directory", "string", "Directory to search in", required=False, default="./workspace"),
    ]

    async def execute(self, **kwargs) -> ToolResult:
        pattern = kwargs.get("pattern", "*")
        directory = kwargs.get("directory", "./workspace")
        try:
            p = Path(directory)
            if not p.exists():
                return ToolResult(success=True, output="Directory not found")
            files = list(p.rglob(pattern))[:100]
            output = "\n".join(str(f) for f in files) if files else "No files found"
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
