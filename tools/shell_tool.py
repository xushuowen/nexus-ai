"""Sandboxed shell command execution tool."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config

logger = logging.getLogger(__name__)

DEFAULT_ALLOWLIST = [
    "ls", "dir", "cat", "head", "tail", "echo", "pwd", "whoami", "date",
    "python", "python3", "pip", "pip3", "node", "npm", "npx",
    "git", "curl", "wget", "which", "where", "find", "grep",
    "wc", "sort", "uniq", "diff", "file", "tree",
]


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
        self._allowlist: list[str] = []

    async def initialize(self) -> None:
        env_list = os.getenv("NEXUS_SHELL_ALLOWLIST", "")
        if env_list:
            self._allowlist = [c.strip() for c in env_list.split(",") if c.strip()]
        else:
            self._allowlist = config.get("security.shell_allowlist", DEFAULT_ALLOWLIST)

    async def validate(self, **kwargs) -> str | None:
        base_err = await super().validate(**kwargs)
        if base_err:
            return base_err

        command = kwargs.get("command", "")
        try:
            parts = shlex.split(command)
        except ValueError:
            return "Invalid command syntax"

        if not parts:
            return "Empty command"

        executable = parts[0].lower().rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if executable not in self._allowlist:
            return f"Command '{executable}' not in allowlist"

        return None

    async def execute(self, **kwargs) -> ToolResult:
        command = kwargs["command"]
        timeout = kwargs.get("timeout", 30)

        try:
            args = shlex.split(command)
        except ValueError as e:
            return ToolResult(success=False, output="", error=f"Invalid command: {e}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
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
