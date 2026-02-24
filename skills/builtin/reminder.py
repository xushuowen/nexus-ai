"""Reminder skill - schedule reminders with natural language time parsing."""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


class ReminderSkill(BaseSkill):
    name = "reminder"
    description = "排程提醒 — 設定、列出、刪除提醒事項"
    triggers = ["提醒", "remind", "鬧鐘", "alarm", "待辦", "todo", "reminder"]
    intent_patterns = [
        r"記住.{0,20}(後|明天|今天|下週|分鐘|小時)",
        r"別忘.{0,10}(要|了)",
        r"(明天|今天|後天|下週).{0,20}(記得|別忘|要去|要交|要做|要開會|要回)",
        r"(幫我|請).{0,5}(記住|提醒我|提醒)",
        r"\d+\s*(分鐘|小時|天)後.{0,10}(叫我|提醒|通知)",
        r"(等一下|等會|晚點|到時候).{0,10}(要|記得|別忘|提醒我)",
        r"(叫我|讓我).{0,5}(記得|不要忘記|記住)",
        r"(下午|晚上|明天早上|今晚|早上).{0,15}(要|記得|別忘|提醒)",
        r"(開會|交作業|繳費|看醫生|吃藥|上課|交報告).{0,10}(提醒|別忘|記得)",
        r"(我要|我需要).{0,5}(記得|記住|提醒自己)",
    ]
    category = "productivity"
    requires_llm = False

    instructions = (
        "提醒系統：\n"
        "1. 設定：「提醒我 30分鐘後 開會」\n"
        "2. 列出：「提醒 列出」或「待辦清單」\n"
        "3. 刪除：「提醒 刪除 1」"
    )

    def __init__(self) -> None:
        self._db_path = config.data_dir() / "reminders.db"
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                remind_at REAL,
                created_at REAL NOT NULL,
                done INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()

        if any(k in text for k in ["列出", "list", "清單", "所有"]):
            return self._list()
        elif any(k in text for k in ["刪除", "delete", "完成", "done", "移除"]):
            return self._delete(query)
        else:
            return self._add(query)

    def _add(self, content: str) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="提醒系統尚未初始化，請稍後再試。", success=False, source=self.name)
        for t in self.triggers:
            content = content.replace(t, "").strip()
        content = content.strip("我 ：:")

        # Parse time from content
        remind_at, cleaned = self._parse_time(content)
        if not cleaned or len(cleaned) < 2:
            return SkillResult(content="請輸入提醒內容，例如：「提醒我 30分鐘後 開會」", success=False, source=self.name)

        now = time.time()
        self._conn.execute(
            "INSERT INTO reminders (content, remind_at, created_at) VALUES (?, ?, ?)",
            (cleaned, remind_at, now),
        )
        self._conn.commit()

        if remind_at:
            dt = datetime.fromtimestamp(remind_at)
            time_str = dt.strftime("%m/%d %H:%M")
            return SkillResult(
                content=f"⏰ 已設定提醒：\n> {cleaned}\n📅 時間：{time_str}",
                success=True, source=self.name,
            )
        return SkillResult(
            content=f"📌 已加入待辦：\n> {cleaned}",
            success=True, source=self.name,
        )

    def _list(self) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="提醒系統尚未初始化，請稍後再試。", success=False, source=self.name)
        rows = self._conn.execute(
            "SELECT id, content, remind_at, done FROM reminders WHERE done = 0 ORDER BY created_at DESC LIMIT 20"
        ).fetchall()

        if not rows:
            return SkillResult(content="📋 目前沒有待辦提醒。", success=True, source=self.name)

        lines = ["📋 待辦提醒：\n"]
        for rid, content, remind_at, done in rows:
            time_str = ""
            if remind_at:
                dt = datetime.fromtimestamp(remind_at)
                time_str = f" ⏰ {dt.strftime('%m/%d %H:%M')}"
            lines.append(f"  [{rid}] {content}{time_str}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _delete(self, query: str) -> SkillResult:
        if self._conn is None:
            return SkillResult(content="提醒系統尚未初始化，請稍後再試。", success=False, source=self.name)
        # Extract ID number
        numbers = re.findall(r'\d+', query)
        if not numbers:
            return SkillResult(content="請指定要刪除的提醒編號，例如：「提醒 刪除 1」", success=False, source=self.name)

        rid = int(numbers[0])
        row = self._conn.execute("SELECT content FROM reminders WHERE id = ?", (rid,)).fetchone()
        if not row:
            return SkillResult(content=f"找不到編號 {rid} 的提醒。", success=False, source=self.name)

        self._conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (rid,))
        self._conn.commit()
        return SkillResult(content=f"✅ 已完成：{row[0]}", success=True, source=self.name)

    def _parse_time(self, text: str) -> tuple[float | None, str]:
        """Parse natural language time. Returns (timestamp, cleaned_text)."""
        now = datetime.now()
        remind_at = None

        # Match combined "X小時Y分鐘後" (e.g. "1小時30分鐘後")
        m_hr = re.search(r'(\d+)\s*小時後?', text)
        m_min = re.search(r'(\d+)\s*分鐘後', text)
        m_day = re.search(r'(\d+)\s*天後', text)

        if m_hr and m_min:
            # Combined: e.g. "1小時30分鐘後"
            hours = int(m_hr.group(1))
            minutes = int(m_min.group(1))
            remind_at = (now + timedelta(hours=hours, minutes=minutes)).timestamp()
            # Remove both patterns from text
            text = re.sub(r'\d+\s*小時後?', '', text)
            text = re.sub(r'\d+\s*分鐘後', '', text)
        elif m_min:
            remind_at = (now + timedelta(minutes=int(m_min.group(1)))).timestamp()
            text = text[:m_min.start()] + text[m_min.end():]
        elif m_hr:
            remind_at = (now + timedelta(hours=int(m_hr.group(1)))).timestamp()
            text = text[:m_hr.start()] + text[m_hr.end():]

        if m_day and not remind_at:
            remind_at = (now + timedelta(days=int(m_day.group(1)))).timestamp()
            text = text[:m_day.start()] + text[m_day.end():]

        # Match "明天" / "後天"
        if "明天" in text:
            tomorrow = now + timedelta(days=1)
            remind_at = tomorrow.replace(hour=9, minute=0, second=0).timestamp()
            text = text.replace("明天", "")
        elif "後天" in text:
            day_after = now + timedelta(days=2)
            remind_at = day_after.replace(hour=9, minute=0, second=0).timestamp()
            text = text.replace("後天", "")

        # Match "下午X點" / "上午X點"
        m = re.search(r'(上午|下午|早上|晚上)?\s*(\d{1,2})\s*[點:時](\d{0,2})', text)
        if m:
            period = m.group(1) or ""
            hour = int(m.group(2))
            minute = int(m.group(3)) if m.group(3) else 0
            if period in ("下午", "晚上") and hour < 12:
                hour += 12
            if remind_at:
                dt = datetime.fromtimestamp(remind_at)
                remind_at = dt.replace(hour=hour, minute=minute, second=0).timestamp()
            else:
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                remind_at = target.timestamp()
            text = text[:m.start()] + text[m.end():]

        return remind_at, text.strip()

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
