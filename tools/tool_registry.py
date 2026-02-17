"""Auto-discovery and context-aware tool activation registry."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Manages tool discovery, registration, and context-aware activation."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def list_by_category(self, category: str) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.category == category]

    def get_function_descriptions(self) -> list[dict[str, Any]]:
        """Get all tool descriptions in OpenAI function-calling format."""
        return [tool.describe_for_llm() for tool in self._tools.values()]

    def get_tools_summary(self) -> str:
        """Get human-readable summary of all tools."""
        return "\n".join(t.short_description() for t in self._tools.values())

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with validation."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(success=False, output="", error=f"Tool '{tool_name}' not found")

        error = await tool.validate(**kwargs)
        if error:
            return ToolResult(success=False, output="", error=error)

        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    async def auto_discover(self, tools_dir: Path | None = None) -> None:
        """Auto-discover and register tools from the tools/ directory."""
        if tools_dir is None:
            tools_dir = Path(__file__).resolve().parent
        for py_file in tools_dir.glob("*_tool.py"):
            module_name = f"nexus.tools.{py_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, BaseTool)
                            and attr is not BaseTool):
                        tool = attr()
                        await tool.initialize()
                        self.register(tool)
            except Exception as e:
                logger.warning(f"Failed to load tool from {py_file}: {e}")

    async def shutdown_all(self) -> None:
        for tool in self._tools.values():
            try:
                await tool.shutdown()
            except Exception:
                pass
        self._tools.clear()
