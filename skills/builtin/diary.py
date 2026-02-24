"""Personal diary skill (inspired by Alex Diary / Stephen Wolfram approach).

Captures daily notes, thoughts, and events into a structured local store.
All data stays local in SQLite - no cloud, no API calls needed.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


class DiarySkill(BaseSkill):
    name = "diary"
    description = "個人日記 — 記錄生活、想法、事件，並可回顧搜尋"
    triggers = ["日記", "diary", "記錄", "record", "筆記", "note", "journal",
                "今天做了", "memo", "備忘"]
    intent_patterns = [
        r"今天.{0,15}(發生|做了|過得|心情|感覺|學到)",
        r"(寫|記錄|紀錄).{0,10}(今天|生活|日記|一下)",
        r"(今天|昨天).{0,10}(想說|想記|覺得|感受)",
        r"幫我.{0,5}記.{0,10}(今天|這件事|這個)",
        r"(最近|這幾天|這週).{0,10}(過得|發生|心情|感覺|狀況)",
        r"(想記|想寫下|想留下).{0,10}(這件事|這個|這段|這些|一下)",
        r"(心情|情緒|感覺).{0,5}(不太好|很好|很累|很開心|很難過|很複雜)",
        r"(回顧|看看|查看).{0,5}(日記|之前|最近的|昨天|上週)",
    ]
    category = "personal"
    requires_llm = False

    instructions = (
        "日記系統支援三種操作：\n"
        "1. 寫入：偵測到記錄意圖時自動存入\n"
        "2. 搜尋：輸入『日記 搜尋 關鍵字』\n"
        "3. 回顧：輸入『日記 回顧』查看最近記錄"
    )

    def __init__(self) -> None:
        self._db_path = config.data_dir() / "diary.db"
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS diary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                timestamp REAL NOT NULL,
                date TEXT NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_diary_date ON diary(date)")
        self._conn.commit()

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()

        # Detect operation
        if any(k in text for k in ["搜尋", "search", "找"]):
            return self._search(query)
        elif any(k in text for k in ["回顧", "review", "最近", "recent"]):
            return self._recent()
        else:
            return self._write(query)

    def _write(self, content: str) -> SkillResult:
        # Strip trigger words from content
        for t in self.triggers:
            content = content.replace(t, "").strip()
        content = content.strip(": ：")

        if not content or len(content) < 2:
            return SkillResult(content="請輸入要記錄的內容。", success=False, source=self.name)

        now = time.time()
        date_str = time.strftime("%Y-%m-%d")
        self._conn.execute(
            "INSERT INTO diary (content, timestamp, date) VALUES (?, ?, ?)",
            (content, now, date_str),
        )
        self._conn.commit()

        time_str = time.strftime("%H:%M")
        return SkillResult(
            content=f"📝 已記錄到日記 [{date_str} {time_str}]\n\n> {content}",
            success=True, source=self.name,
        )

    def _search(self, query: str) -> SkillResult:
        # Extract search keywords
        for prefix in ["搜尋", "search", "找", "日記"]:
            query = query.replace(prefix, "").strip()
        query = query.strip()

        if not query:
            return SkillResult(content="請提供搜尋關鍵字。", success=False, source=self.name)

        rows = self._conn.execute(
            "SELECT content, date FROM diary WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 10",
            (f"%{query}%",),
        ).fetchall()

        if not rows:
            return SkillResult(content=f"找不到包含「{query}」的日記。", success=True, source=self.name)

        lines = [f"🔍 搜尋「{query}」找到 {len(rows)} 筆：\n"]
        for content, date in rows:
            lines.append(f"[{date}] {content[:100]}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _recent(self) -> SkillResult:
        rows = self._conn.execute(
            "SELECT content, date FROM diary ORDER BY timestamp DESC LIMIT 10"
        ).fetchall()

        if not rows:
            return SkillResult(content="還沒有任何日記記錄。", success=True, source=self.name)

        lines = ["📖 最近的日記：\n"]
        for content, date in rows:
            lines.append(f"[{date}] {content[:100]}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
