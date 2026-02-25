"""Schedule Runner — 每分鐘檢查循環排程，時間到就執行並透過 Telegram 通知。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


class ScheduleRunner:
    """Background runner that checks auto_schedule entries every minute."""

    def __init__(self, skill, orchestrator, telegram) -> None:
        self._skill = skill          # AutoScheduleSkill instance
        self._orchestrator = orchestrator
        self._telegram = telegram
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())
        logger.info("ScheduleRunner started.")

    def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        while True:
            try:
                await self._check_all()
            except Exception as e:
                logger.error(f"ScheduleRunner loop error: {e}")

            # Sleep until the top of the next minute (max 60s, min 1s)
            now = datetime.now()
            sleep_secs = max(1, 60 - now.second)
            await asyncio.sleep(sleep_secs)

    async def _check_all(self) -> None:
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_date = now.strftime("%Y-%m-%d")
        today_weekday = now.weekday()  # 0=Mon … 6=Sun

        for sched in self._skill.get_schedules():
            if not sched.enabled:
                continue
            if sched.time != current_time:
                continue
            if sched.last_run_date == today_date:
                continue  # Already ran today
            if not self._is_today(sched.days, today_weekday):
                continue

            logger.info(f"ScheduleRunner firing: {sched.name}")
            asyncio.create_task(self._fire(sched, today_date))

    def _is_today(self, days: str, today_weekday: int) -> bool:
        if days == "daily":
            return True
        if days == "weekdays":
            return today_weekday < 5
        if days == "weekends":
            return today_weekday >= 5
        # e.g. "mon,wed,fri"
        for d in days.split(","):
            d = d.strip()
            if d in WEEKDAY_MAP and WEEKDAY_MAP[d] == today_weekday:
                return True
        return False

    async def _fire(self, sched, today_date: str) -> None:
        try:
            result_text = ""
            async for event in self._orchestrator.process(
                sched.action, session_id="schedule_runner"
            ):
                if event.event_type == "final_answer":
                    result_text = event.content

            if result_text:
                await self._telegram.send_to_owner(
                    f"⏰ **自動排程：{sched.name}**\n\n{result_text}"
                )

            self._skill.update_last_run(sched.id, today_date)
            logger.info(f"ScheduleRunner: '{sched.name}' done.")
        except Exception as e:
            logger.error(f"ScheduleRunner: '{sched.name}' failed: {e}")
