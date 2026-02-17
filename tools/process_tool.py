"""Process management tool - OpenClaw-style background session management.
Run, monitor, and control background processes."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config

logger = logging.getLogger(__name__)


class BackgroundProcess:
    def __init__(self, pid: str, command: str, proc: asyncio.subprocess.Process):
        self.pid = pid
        self.command = command
        self.proc = proc
        self.started_at = time.time()
        self.output_buffer: list[str] = []


class ProcessTool(BaseTool):
    name = "process"
    description = "Manage background processes: start, list, read output, kill (OpenClaw-style)"
    category = "system"
    parameters = [
        ToolParameter("action", "string",
                       "Action: 'start', 'list', 'log', 'kill'",
                       enum=["start", "list", "log", "kill"]),
        ToolParameter("command", "string", "Shell command to run in background (for 'start')", required=False),
        ToolParameter("pid", "string", "Process ID (for 'log' and 'kill')", required=False),
    ]

    def __init__(self) -> None:
        self._processes: dict[str, BackgroundProcess] = {}

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "start":
            return await self._start(kwargs.get("command", ""))
        elif action == "list":
            return self._list()
        elif action == "log":
            return self._log(kwargs.get("pid", ""))
        elif action == "kill":
            return await self._kill(kwargs.get("pid", ""))
        return ToolResult(success=False, output="", error="Unknown action")

    async def _start(self, command: str) -> ToolResult:
        if not command:
            return ToolResult(success=False, output="", error="Command required")

        # Safety check
        from nexus.security.sandbox import Sandbox
        sandbox = Sandbox()
        safe, reason = sandbox.is_command_safe(command)
        if not safe:
            return ToolResult(success=False, output="", error=f"Blocked: {reason}")

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(config.data_dir()),
            )
            pid = f"bg_{int(time.time())}_{proc.pid}"
            bp = BackgroundProcess(pid, command, proc)
            self._processes[pid] = bp

            # Start output reader
            asyncio.create_task(self._read_output(bp))

            return ToolResult(success=True, output=f"Started background process\nPID: {pid}\nCommand: {command}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _list(self) -> ToolResult:
        if not self._processes:
            return ToolResult(success=True, output="No background processes.")
        lines = []
        for bp in self._processes.values():
            running = bp.proc.returncode is None
            status = "running" if running else f"exited ({bp.proc.returncode})"
            age = int(time.time() - bp.started_at)
            lines.append(f"[{bp.pid}] {status} | {age}s | {bp.command[:60]}")
        return ToolResult(success=True, output="\n".join(lines))

    def _log(self, pid: str) -> ToolResult:
        bp = self._processes.get(pid)
        if not bp:
            return ToolResult(success=False, output="", error=f"Process {pid} not found")
        output = "\n".join(bp.output_buffer[-50:])
        return ToolResult(success=True, output=output or "(no output yet)")

    async def _kill(self, pid: str) -> ToolResult:
        bp = self._processes.get(pid)
        if not bp:
            return ToolResult(success=False, output="", error=f"Process {pid} not found")
        try:
            bp.proc.kill()
            await bp.proc.wait()
            del self._processes[pid]
            return ToolResult(success=True, output=f"Killed process {pid}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    async def _read_output(self, bp: BackgroundProcess) -> None:
        """Read stdout in background."""
        try:
            while True:
                line = await bp.proc.stdout.readline()
                if not line:
                    break
                bp.output_buffer.append(line.decode(errors="replace").rstrip())
                if len(bp.output_buffer) > 500:
                    bp.output_buffer = bp.output_buffer[-200:]
        except Exception:
            pass

    async def shutdown(self) -> None:
        for bp in self._processes.values():
            try:
                bp.proc.kill()
            except Exception:
                pass
        self._processes.clear()
