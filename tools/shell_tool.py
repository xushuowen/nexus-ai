"""Sandboxed shell command execution tool."""

from __future__ import annotations

import asyncio
import logging

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config

logger = logging.getLogger(__name__)


class ShellTool(BaseTool):
    name = "shell"
    description = "Execute a shell command in a sandboxed environment"
    category = "system"
    requires_confirmation = True
    parameters = [
        ToolParameter("command", "string", "The shell command to execute"),
        ToolParameter("timeout", "integer", "Timeout in seconds", required=False, default=30),
    ]

    def __init__(self) -> None:
        self._blocked: list[str] = []

    async def initialize(self) -> None:
        self._blocked = config.get("security.blocked_commands", [])

    async def validate(self, **kwargs) -> str | None:
        base_err = await super().validate(**kwargs)
        if base_err:
            return base_err
        cmd = kwargs.get("command", "").lower()
        for blocked in self._blocked:
            if blocked.lower() in cmd:
                return f"Command contains blocked pattern: {blocked}"
        dangerous = ["rm -rf /", "format", "mkfs", "dd if=", ":(){ :|:& };:"]
        for d in dangerous:
            if d in cmd:
                return f"Dangerous command blocked"
        return None

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", 30)

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(config.data_dir()),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\n[stderr] " + stderr.decode(errors="replace")
            return ToolResult(success=proc.returncode == 0, output=output[:5000])
        except asyncio.TimeoutError:
            return ToolResult(success=False, output="", error="Command timed out")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
