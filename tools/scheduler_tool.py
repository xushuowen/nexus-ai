"""Scheduled task execution tool - cron-like heartbeat daemon pattern."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config

logger = logging.getLogger(__name__)


class SchedulerTool(BaseTool):
    name = "scheduler"
    description = "Schedule and manage recurring tasks"
    category = "system"
    parameters = [
        ToolParameter("action", "string", "Action: 'add', 'list', 'remove', 'status'",
                       enum=["add", "list", "remove", "status"]),
        ToolParameter("task_name", "string", "Name for the scheduled task", required=False),
        ToolParameter("interval_minutes", "integer", "Run interval in minutes", required=False, default=60),
        ToolParameter("command", "string", "Command or action to execute", required=False),
        ToolParameter("task_id", "string", "Task ID for removal", required=False),
    ]

    def __init__(self) -> None:
        self._tasks: dict[str, dict[str, Any]] = {}
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._tasks_path = config.data_dir() / "scheduled_tasks.json"

    async def initialize(self) -> None:
        if self._tasks_path.exists():
            try:
                self._tasks = json.loads(self._tasks_path.read_text(encoding="utf-8"))
            except Exception:
                self._tasks = {}

    def _save(self) -> None:
        self._tasks_path.write_text(json.dumps(self._tasks, indent=2), encoding="utf-8")

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "list" or action == "status":
            if not self._tasks:
                return ToolResult(success=True, output="No scheduled tasks.")
            lines = []
            for tid, task in self._tasks.items():
                status = "running" if tid in self._running_tasks else "stopped"
                lines.append(
                    f"[{tid}] {task['name']} - every {task['interval_min']}min - {status}"
                )
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "add":
            name = kwargs.get("task_name", "unnamed")
            interval = kwargs.get("interval_minutes", 60)
            command = kwargs.get("command", "")
            task_id = f"sched_{int(time.time())}"
            self._tasks[task_id] = {
                "name": name,
                "interval_min": interval,
                "command": command,
                "created_at": time.time(),
            }
            self._save()
            return ToolResult(success=True, output=f"Scheduled '{name}' every {interval}min (ID: {task_id})")

        elif action == "remove":
            task_id = kwargs.get("task_id", "")
            if task_id in self._running_tasks:
                self._running_tasks[task_id].cancel()
                del self._running_tasks[task_id]
            self._tasks.pop(task_id, None)
            self._save()
            return ToolResult(success=True, output=f"Removed task {task_id}")

        return ToolResult(success=False, output="", error="Unknown action")

    async def shutdown(self) -> None:
        for task in self._running_tasks.values():
            task.cancel()
        self._running_tasks.clear()
