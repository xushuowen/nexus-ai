"""Sandboxed shell command execution specialist agent."""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent
from nexus import config

logger = logging.getLogger(__name__)

# Default safe command prefixes (allowlist approach)
DEFAULT_ALLOWLIST = [
    "ls", "dir", "cat", "head", "tail", "echo", "pwd", "whoami", "date",
    "python", "python3", "pip", "pip3", "node", "npm", "npx",
    "git", "curl", "wget", "which", "where", "find", "grep",
    "wc", "sort", "uniq", "diff", "file", "tree",
]


class ShellAgent(BaseAgent):
    name = "shell"
    description = "Sandboxed shell command execution"
    capabilities = [AgentCapability.SHELL]
    priority = 4

    def __init__(self) -> None:
        super().__init__()
        self._allowlist: list[str] = []

    async def initialize(self) -> None:
        await super().initialize()
        # Load allowlist from env or config
        env_list = os.getenv("NEXUS_SHELL_ALLOWLIST", "")
        if env_list:
            self._allowlist = [c.strip() for c in env_list.split(",") if c.strip()]
        else:
            self._allowlist = config.get("security.shell_allowlist", DEFAULT_ALLOWLIST)

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["run", "execute", "command", "shell", "terminal", "cmd",
                     "pip", "npm", "git", "ls", "dir", "cd"]
        return min(1.0, sum(0.15 for kw in keywords if kw in text))

    # Dangerous argument patterns to block even for allowed executables
    _DANGEROUS_ARG_PATTERNS = [
        re.compile(r'^\s*-c\s*$'),         # python -c / node -c (inline code execution)
        re.compile(r'^\s*-e\s*$'),          # node -e (eval)
        re.compile(r'__import__'),
        re.compile(r'exec\s*\('),
        re.compile(r'eval\s*\('),
        re.compile(r'os\.system'),
        re.compile(r'subprocess'),
        re.compile(r'shutil\.rmtree'),
        re.compile(r'rm\s+-rf'),
        re.compile(r':(){ :|:& }'),         # fork bomb
    ]

    def _is_allowed(self, command: str) -> tuple[bool, str]:
        """Check command against allowlist. Returns (allowed, reason)."""
        try:
            parts = shlex.split(command)
        except ValueError:
            return False, "Invalid command syntax"

        if not parts:
            return False, "Empty command"

        executable = parts[0].lower()
        # Strip path prefix (e.g. /usr/bin/python -> python)
        executable = executable.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        if executable not in self._allowlist:
            return False, f"Command '{executable}' not in allowlist. Allowed: {', '.join(self._allowlist[:10])}..."

        # Block dangerous argument patterns (e.g. python -c "malicious code")
        for i, arg in enumerate(parts[1:], 1):
            for pattern in self._DANGEROUS_ARG_PATTERNS:
                if pattern.search(arg):
                    return False, f"Dangerous argument pattern blocked: '{arg}'"

        return True, ""

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        command = self._extract_command(message.content)
        if not command:
            return AgentResult(
                content="Please specify a command to execute. Example: 'run: ls -la'",
                confidence=0.3, source_agent=self.name,
            )

        allowed, reason = self._is_allowed(command)
        if not allowed:
            return AgentResult(
                content=f"Command blocked: {reason}",
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
        for prefix in ["run:", "execute:", "command:", "$", ">"]:
            if prefix in text.lower():
                idx = text.lower().index(prefix) + len(prefix)
                return text[idx:].strip()
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 2:
                cmd = parts[1].strip()
                if cmd.startswith("bash") or cmd.startswith("sh"):
                    cmd = cmd.split("\n", 1)[-1]
                return cmd.strip()
        return None

    async def _execute(self, command: str, timeout: int = 30) -> str:
        """Execute using subprocess_exec (not shell) for safety."""
        try:
            args = shlex.split(command)
        except ValueError as e:
            return f"Invalid command: {e}"

        proc = await asyncio.create_subprocess_exec(
            *args,
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
