"""Pomodoro timer skill - track focus sessions with SQLite."""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


class PomodoroSkill(BaseSkill):
    name = "pomodoro"
    description = "番茄鐘 — 專注計時、記錄工作時段"
    triggers = ["番茄鐘", "pomodoro", "計時", "timer", "專注", "focus"]
    intent_patterns = [
        r"(我要|幫我|開始).{0,5}(專注|讀書|工作|計時|番茄)",
        r"(專注|讀書|工作).{0,5}(25分鐘|一個番茄|計時器|模式)",
        r"(休息|停止|結束).{0,5}(計時|番茄|專注)",
        r"(今天|這週).{0,5}(專注了幾|幾個番茄|讀了多久)",
    ]
    category = "productivity"
    requires_llm = False

    instructions = (
        "番茄鐘（25 分鐘工作 + 5 分鐘休息）：\n"
        "1. 開始：「番茄鐘 開始」或「番茄鐘 開始 讀書」\n"
        "2. 結束：「番茄鐘 結束」\n"
        "3. 統計：「番茄鐘 統計」"
    )

    WORK_MINUTES = 25
    BREAK_MINUTES = 5

    def __init__(self) -> None:
        self._db_path = config.data_dir() / "pomodoro.db"
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS pomodoro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task TEXT DEFAULT '',
                started_at REAL NOT NULL,
                ended_at REAL,
                duration_min REAL DEFAULT 0,
                date TEXT NOT NULL,
                completed INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()

        if any(k in text for k in ["統計", "stats", "今天", "today", "記錄"]):
            return self._stats()
        elif any(k in text for k in ["結束", "stop", "end", "完成", "done"]):
            return self._stop()
        else:
            return self._start(query)

    def _start(self, query: str) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="番茄鐘系統尚未初始化，請稍後再試。", success=False, source=self.name)
        # Check if there's already an active session
        active = self._conn.execute(
            "SELECT id, task, started_at FROM pomodoro WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if active:
            elapsed = (time.time() - active[2]) / 60
            return SkillResult(
                content=f"⚠️ 已有進行中的番茄鐘：「{active[1] or '工作'}」\n⏱️ 已經過 {elapsed:.0f} 分鐘\n\n輸入「番茄鐘 結束」來完成。",
                success=True, source=self.name,
            )

        # Extract task name
        task = query
        for t in self.triggers + ["開始", "start", "begin"]:
            task = task.replace(t, "").strip()
        task = task.strip(" ：:") or "工作"

        now = time.time()
        date_str = time.strftime("%Y-%m-%d")
        self._conn.execute(
            "INSERT INTO pomodoro (task, started_at, date) VALUES (?, ?, ?)",
            (task, now, date_str),
        )
        self._conn.commit()

        return SkillResult(
            content=(
                f"🍅 番茄鐘開始！\n"
                f"📝 任務：{task}\n"
                f"⏱️ 時間：{self.WORK_MINUTES} 分鐘\n"
                f"🕐 開始：{time.strftime('%H:%M')}\n\n"
                f"專注工作吧！完成後輸入「番茄鐘 結束」。"
            ),
            success=True, source=self.name,
        )

    def _stop(self) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="番茄鐘系統尚未初始化，請稍後再試。", success=False, source=self.name)
        active = self._conn.execute(
            "SELECT id, task, started_at FROM pomodoro WHERE ended_at IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()

        if not active:
            return SkillResult(content="目前沒有進行中的番茄鐘。", success=False, source=self.name)

        now = time.time()
        duration = (now - active[2]) / 60
        completed = 1 if duration >= self.WORK_MINUTES * 0.8 else 0

        self._conn.execute(
            "UPDATE pomodoro SET ended_at = ?, duration_min = ?, completed = ? WHERE id = ?",
            (now, duration, completed, active[0]),
        )
        self._conn.commit()

        status = "✅ 完成" if completed else "⏸️ 提前結束"
        return SkillResult(
            content=(
                f"🍅 番茄鐘{status}！\n"
                f"📝 任務：{active[1] or '工作'}\n"
                f"⏱️ 時長：{duration:.0f} 分鐘\n\n"
                f"{'☕ 休息 5 分鐘吧！' if completed else '下次繼續加油！'}"
            ),
            success=True, source=self.name,
        )

    def _stats(self) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="番茄鐘系統尚未初始化，請稍後再試。", success=False, source=self.name)
        today = time.strftime("%Y-%m-%d")

        today_rows = self._conn.execute(
            "SELECT task, duration_min, completed FROM pomodoro WHERE date = ? AND ended_at IS NOT NULL",
            (today,),
        ).fetchall()

        total_rows = self._conn.execute(
            "SELECT COUNT(*), SUM(duration_min), SUM(completed) FROM pomodoro WHERE ended_at IS NOT NULL"
        ).fetchone()

        lines = [f"📊 **番茄鐘統計**\n"]

        if today_rows:
            today_total = sum(r[1] for r in today_rows)
            today_completed = sum(1 for r in today_rows if r[2])
            lines.append(f"**今日 ({today})**:")
            lines.append(f"  🍅 完成: {today_completed} 個番茄鐘")
            lines.append(f"  ⏱️ 總時間: {today_total:.0f} 分鐘")
            lines.append("")
            for task, dur, comp in today_rows:
                icon = "✅" if comp else "⏸️"
                lines.append(f"  {icon} {task or '工作'} — {dur:.0f} 分")
        else:
            lines.append(f"今日 ({today}) 尚無記錄。")

        if total_rows and total_rows[0]:
            lines.append(f"\n**累計**: {total_rows[0]} 次，{total_rows[1]:.0f} 分鐘，完成 {total_rows[2] or 0} 個")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
