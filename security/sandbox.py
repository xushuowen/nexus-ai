"""Command execution sandbox with safety checks."""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)


class Sandbox:
    """Sandboxed environment for executing commands safely."""

    def __init__(self) -> None:
        cfg = config.load_config().get("security", {})
        self.enabled = cfg.get("sandbox_enabled", True)
        self._blocked_commands: list[str] = cfg.get("blocked_commands", [])
        self._blocked_patterns: list[re.Pattern] = [
            re.compile(r'rm\s+-rf\s+/', re.IGNORECASE),
            re.compile(r'format\s+[a-z]:', re.IGNORECASE),
            re.compile(r'del\s+/[fF]\s+/[sS]', re.IGNORECASE),
            re.compile(r'mkfs', re.IGNORECASE),
            re.compile(r'dd\s+if=', re.IGNORECASE),
            re.compile(r':\(\)\{.*\|.*&\s*\};:', re.IGNORECASE),  # Fork bomb
            re.compile(r'>\s*/dev/sd', re.IGNORECASE),
            re.compile(r'chmod\s+777\s+/', re.IGNORECASE),
            re.compile(r'curl.*\|\s*(ba)?sh', re.IGNORECASE),  # Pipe to shell
        ]

    def is_command_safe(self, command: str) -> tuple[bool, str]:
        """Check if a command is safe to execute. Returns (safe, reason)."""
        if not self.enabled:
            return True, ""

        cmd_lower = command.lower().strip()

        # Check blocked commands list
        for blocked in self._blocked_commands:
            if blocked.lower() in cmd_lower:
                return False, f"Command contains blocked pattern: {blocked}"

        # Check regex patterns
        for pattern in self._blocked_patterns:
            if pattern.search(command):
                return False, f"Command matches dangerous pattern"

        return True, ""

    async def execute(
        self,
        command: str,
        cwd: str | None = None,
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Execute a command in the sandbox."""
        safe, reason = self.is_command_safe(command)
        if not safe:
            return {"success": False, "output": "", "error": reason}

        work_dir = cwd or str(config.data_dir())
        environment = {**os.environ, **(env or {})}

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
                env=environment,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "success": proc.returncode == 0,
                "output": stdout.decode(errors="replace")[:10000],
                "stderr": stderr.decode(errors="replace")[:5000],
                "returncode": proc.returncode,
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "output": "", "error": "Timed out"}
        except Exception as e:
            return {"success": False, "output": "", "error": str(e)}
