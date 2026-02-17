"""Cron job management tool - OpenClaw-style scheduled automation.
Supports recurring tasks with natural language scheduling."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Awaitable

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config

logger = logging.getLogger(__name__)


class CronJob:
    def __init__(self, job_id: str, name: str, action: str, interval_sec: int, enabled: bool = True):
        self.job_id = job_id
        self.name = name
        self.action = action  # The instruction/prompt to execute
        self.interval_sec = interval_sec
        self.enabled = enabled
        self.last_run: float = 0
        self.run_count: int = 0
        self.created_at: float = time.time()


class CronTool(BaseTool):
    name = "cron"
    description = "Manage scheduled recurring tasks (OpenClaw-style cron jobs)"
    category = "automation"
    parameters = [
        ToolParameter("action", "string", "Action: 'create', 'list', 'delete', 'pause', 'resume'",
                       enum=["create", "list", "delete", "pause", "resume"]),
        ToolParameter("name", "string", "Job name", required=False),
        ToolParameter("instruction", "string", "What to do each run (natural language)", required=False),
        ToolParameter("interval", "string", "Interval: '5m', '1h', '30m', '1d'", required=False, default="1h"),
        ToolParameter("job_id", "string", "Job ID for delete/pause/resume", required=False),
    ]

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._executor: Callable | None = None  # async callable(instruction) -> str
        self._state_path = config.data_dir() / "cron_jobs.json"

    def set_executor(self, executor: Callable[..., Awaitable[str]]) -> None:
        """Set the function that executes cron job instructions."""
        self._executor = executor

    async def initialize(self) -> None:
        self._load_state()

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                for jd in data:
                    job = CronJob(jd["id"], jd["name"], jd["action"], jd["interval_sec"], jd.get("enabled", True))
                    job.run_count = jd.get("run_count", 0)
                    self._jobs[job.job_id] = job
            except Exception as e:
                logger.warning(f"Cron state load error: {e}")

    def _save_state(self) -> None:
        data = []
        for job in self._jobs.values():
            data.append({
                "id": job.job_id,
                "name": job.name,
                "action": job.action,
                "interval_sec": job.interval_sec,
                "enabled": job.enabled,
                "run_count": job.run_count,
            })
        self._state_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _parse_interval(self, interval_str: str) -> int:
        """Parse '5m', '1h', '30m', '1d' to seconds."""
        s = interval_str.strip().lower()
        if s.endswith("m"):
            return int(s[:-1]) * 60
        elif s.endswith("h"):
            return int(s[:-1]) * 3600
        elif s.endswith("d"):
            return int(s[:-1]) * 86400
        elif s.endswith("s"):
            return int(s[:-1])
        else:
            return int(s) * 60  # default to minutes

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "list":
            return self._list_jobs()
        elif action == "create":
            return self._create_job(
                kwargs.get("name", "unnamed"),
                kwargs.get("instruction", ""),
                kwargs.get("interval", "1h"),
            )
        elif action == "delete":
            return self._delete_job(kwargs.get("job_id", ""))
        elif action == "pause":
            return self._toggle_job(kwargs.get("job_id", ""), enabled=False)
        elif action == "resume":
            return self._toggle_job(kwargs.get("job_id", ""), enabled=True)
        return ToolResult(success=False, output="", error="Unknown action")

    def _list_jobs(self) -> ToolResult:
        if not self._jobs:
            return ToolResult(success=True, output="No cron jobs scheduled.")
        lines = []
        for job in self._jobs.values():
            status = "active" if job.enabled else "paused"
            lines.append(
                f"[{job.job_id}] {job.name} | {status} | every {job.interval_sec}s | runs: {job.run_count}\n"
                f"  -> {job.action[:80]}"
            )
        return ToolResult(success=True, output="\n\n".join(lines))

    def _create_job(self, name: str, instruction: str, interval: str) -> ToolResult:
        if not instruction:
            return ToolResult(success=False, output="", error="Instruction required")
        job_id = f"cron_{int(time.time())}"
        interval_sec = self._parse_interval(interval)
        job = CronJob(job_id, name, instruction, interval_sec)
        self._jobs[job_id] = job
        self._save_state()

        # Start the job loop if executor is set
        if self._executor:
            self._tasks[job_id] = asyncio.create_task(self._run_loop(job))

        return ToolResult(success=True, output=f"Created cron job '{name}' (ID: {job_id}), runs every {interval}")

    def _delete_job(self, job_id: str) -> ToolResult:
        if job_id in self._tasks:
            self._tasks[job_id].cancel()
            del self._tasks[job_id]
        if job_id in self._jobs:
            del self._jobs[job_id]
            self._save_state()
            return ToolResult(success=True, output=f"Deleted job {job_id}")
        return ToolResult(success=False, output="", error=f"Job {job_id} not found")

    def _toggle_job(self, job_id: str, enabled: bool) -> ToolResult:
        job = self._jobs.get(job_id)
        if not job:
            return ToolResult(success=False, output="", error=f"Job {job_id} not found")
        job.enabled = enabled
        self._save_state()
        return ToolResult(success=True, output=f"Job {job_id} {'resumed' if enabled else 'paused'}")

    async def _run_loop(self, job: CronJob) -> None:
        """Background loop for a cron job."""
        while True:
            try:
                await asyncio.sleep(job.interval_sec)
                if not job.enabled or not self._executor:
                    continue
                logger.info(f"Cron executing: {job.name}")
                result = await self._executor(job.action)
                job.run_count += 1
                job.last_run = time.time()
                self._save_state()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cron job '{job.name}' error: {e}")

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()
