"""Session management tool - OpenClaw-style session spawn/list/send.
Enables sub-agent runs and multi-session management."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class SubSession:
    def __init__(self, session_id: str, instruction: str):
        self.session_id = session_id
        self.instruction = instruction
        self.status = "running"
        self.result = ""
        self.started_at = time.time()


class SessionTool(BaseTool):
    name = "sessions"
    description = "Manage sub-agent sessions: spawn parallel tasks, check status, get results"
    category = "orchestration"
    parameters = [
        ToolParameter("action", "string",
                       "Action: 'spawn', 'list', 'status', 'result'",
                       enum=["spawn", "list", "status", "result"]),
        ToolParameter("instruction", "string", "Task instruction for spawned session", required=False),
        ToolParameter("session_id", "string", "Session ID to check", required=False),
    ]

    def __init__(self) -> None:
        self._sessions: dict[str, SubSession] = {}
        self._executor = None  # async callable(instruction) -> str

    def set_executor(self, executor) -> None:
        self._executor = executor

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "spawn":
            return await self._spawn(kwargs.get("instruction", ""))
        elif action == "list":
            return self._list()
        elif action == "status":
            return self._status(kwargs.get("session_id", ""))
        elif action == "result":
            return self._result(kwargs.get("session_id", ""))
        return ToolResult(success=False, output="", error="Unknown action")

    async def _spawn(self, instruction: str) -> ToolResult:
        if not instruction:
            return ToolResult(success=False, output="", error="Instruction required")
        if not self._executor:
            return ToolResult(success=False, output="", error="Executor not configured")

        sid = f"sub_{int(time.time())}"
        sub = SubSession(sid, instruction)
        self._sessions[sid] = sub

        # Run in background
        asyncio.create_task(self._run_session(sub))

        return ToolResult(success=True, output=f"Spawned sub-session: {sid}\nInstruction: {instruction[:100]}")

    def _list(self) -> ToolResult:
        if not self._sessions:
            return ToolResult(success=True, output="No active sub-sessions.")
        lines = []
        for sub in self._sessions.values():
            age = int(time.time() - sub.started_at)
            lines.append(f"[{sub.session_id}] {sub.status} | {age}s | {sub.instruction[:60]}")
        return ToolResult(success=True, output="\n".join(lines))

    def _status(self, sid: str) -> ToolResult:
        sub = self._sessions.get(sid)
        if not sub:
            return ToolResult(success=False, output="", error=f"Session {sid} not found")
        return ToolResult(success=True, output=f"Status: {sub.status}\nInstruction: {sub.instruction}")

    def _result(self, sid: str) -> ToolResult:
        sub = self._sessions.get(sid)
        if not sub:
            return ToolResult(success=False, output="", error=f"Session {sid} not found")
        if sub.status == "running":
            return ToolResult(success=True, output="Still running... check back later.")
        return ToolResult(success=True, output=sub.result or "(no result)")

    async def _run_session(self, sub: SubSession) -> None:
        try:
            result = await self._executor(sub.instruction)
            sub.result = result
            sub.status = "completed"
        except Exception as e:
            sub.result = f"Error: {e}"
            sub.status = "failed"
