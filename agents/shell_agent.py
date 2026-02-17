"""Sandboxed shell command execution specialist agent."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent
from nexus import config

logger = logging.getLogger(__name__)


class ShellAgent(BaseAgent):
    name = "shell"
    description = "Sandboxed shell command execution"
    capabilities = [AgentCapability.SHELL]
    priority = 4

    def __init__(self) -> None:
        super().__init__()
        self._blocked_commands: list[str] = []

    async def initialize(self) -> None:
        await super().initialize()
        self._blocked_commands = config.get("security.blocked_commands", [])

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["run", "execute", "command", "shell", "terminal", "cmd",
                     "pip", "npm", "git", "ls", "dir", "cd"]
        return min(1.0, sum(0.15 for kw in keywords if kw in text))

    def _is_safe(self, command: str) -> bool:
        cmd_lower = command.lower().strip()
        for blocked in self._blocked_commands:
            if blocked.lower() in cmd_lower:
                return False
        # Block dangerous patterns
        dangerous = ["rm -rf", "format c:", "del /f /s", ":(){ :|:& };:",
                      "mkfs", "dd if=", "> /dev/sd"]
        for d in dangerous:
            if d in cmd_lower:
                return False
        return True

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        # Extract command from message
        command = self._extract_command(message.content)
        if not command:
            return AgentResult(
                content="Please specify a command to execute. Example: 'run: ls -la'",
                confidence=0.3, source_agent=self.name,
            )

        if not self._is_safe(command):
            return AgentResult(
                content=f"Command blocked for safety: `{command}`",
                confidence=0.9, source_agent=self.name,
            )

        try:
            result = await self._execute(command)
            return AgentResult(
                content=f"```\n$ {command}\n{result}\n```",
                confidence=0.9, source_agent=self.name,
            )
        except Exception as e:
            return AgentResult(
                content=f"Command failed: {e}",
                confidence=0.5, source_agent=self.name,
            )

    def _extract_command(self, text: str) -> str | None:
        # Try "run: <cmd>" or "execute: <cmd>" patterns
        for prefix in ["run:", "execute:", "command:", "$", ">"]:
            if prefix in text.lower():
                idx = text.lower().index(prefix) + len(prefix)
                return text[idx:].strip()
        # Try code blocks
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                cmd = parts[1].strip()
                if cmd.startswith("bash") or cmd.startswith("sh"):
                    cmd = cmd.split("\n", 1)[-1]
                return cmd.strip()
        return None

    async def _execute(self, command: str, timeout: int = 30) -> str:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(config.data_dir()),
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\nSTDERR:\n" + stderr.decode(errors="replace")
            return output[:5000]
        except asyncio.TimeoutError:
            proc.kill()
            return "Command timed out."
