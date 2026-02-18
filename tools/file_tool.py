"""File read/write/search operations tool (protected by filesystem_scope)."""

from __future__ import annotations

from pathlib import Path

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus.security.filesystem_scope import FilesystemScope

# Shared scope checker
_scope = FilesystemScope()


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

        ok, reason = _scope.check_read(path)
        if not ok:
            return ToolResult(success=False, output="", error=reason)

        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[:max_lines]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


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

        ok, reason = _scope.check_write(path)
        if not ok:
            return ToolResult(success=False, output="", error=reason)

        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with p.open(mode, encoding="utf-8") as f:
                f.write(content)
            return ToolResult(success=True, output=f"Written to {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


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

        if not _scope.is_allowed(directory):
            return ToolResult(success=False, output="", error=f"Directory {directory} is outside allowed scope")

        try:
            p = Path(directory)
            if not p.exists():
                return ToolResult(success=True, output="Directory not found")
            files = list(p.rglob(pattern))[:100]
            output = "\n".join(str(f) for f in files) if files else "No files found"
            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
