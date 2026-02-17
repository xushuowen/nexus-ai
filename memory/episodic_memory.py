"""Layer 2: Episodic Memory - Recent interactions with auto-distilled lessons.
Uses SQLite for persistence. Low token cost (only for lesson extraction)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus import config


@dataclass
class Episode:
    id: int
    query: str
    response: str
    lesson: str
    confidence: float
    timestamp: float
    metadata: dict[str, Any]


class EpisodicMemory:
    """Stores recent interactions and auto-extracts lessons learned."""

    def __init__(self, db_path: Path | None = None, max_entries: int | None = None) -> None:
        self.db_path = db_path or Path(config.get("memory.sqlite_path", "./data/nexus.db"))
        self.max_entries = max_entries or config.get("memory.episodic_max_entries", 1000)
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                lesson TEXT DEFAULT '',
                confidence REAL DEFAULT 0.5,
                timestamp REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_episodes_ts ON episodes(timestamp DESC)
        """)
        self._conn.commit()

    async def store(
        self,
        query: str,
        response: str,
        lesson: str = "",
        confidence: float = 0.5,
        metadata: dict | None = None,
    ) -> int:
        """Store an interaction episode."""
        cursor = self._conn.execute(
            "INSERT INTO episodes (query, response, lesson, confidence, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (query, response, lesson, confidence, time.time(), json.dumps(metadata or {})),
        )
        self._conn.commit()
        await self._enforce_limit()
        return cursor.lastrowid

    async def search(self, query: str, limit: int = 5) -> list[Episode]:
        """Search episodes by keyword matching."""
        rows = self._conn.execute(
            "SELECT id, query, response, lesson, confidence, timestamp, metadata "
            "FROM episodes WHERE query LIKE ? OR response LIKE ? OR lesson LIKE ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", f"%{query}%", limit),
        ).fetchall()
        return [self._row_to_episode(r) for r in rows]

    async def get_recent(self, limit: int = 10) -> list[Episode]:
        """Get most recent episodes."""
        rows = self._conn.execute(
            "SELECT id, query, response, lesson, confidence, timestamp, metadata "
            "FROM episodes ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_episode(r) for r in rows]

    async def get_lessons(self, limit: int = 20) -> list[str]:
        """Get distilled lessons from past episodes."""
        rows = self._conn.execute(
            "SELECT lesson FROM episodes WHERE lesson != '' ORDER BY confidence DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [r[0] for r in rows]

    async def extract_lesson(self, query: str, response: str, llm_call=None) -> str:
        """Extract a lesson from an interaction. Uses LLM if provided, else simple heuristic."""
        if llm_call:
            prompt = (
                f"Extract a brief, reusable lesson from this interaction:\n"
                f"Q: {query[:200]}\nA: {response[:300]}\n"
                f"Lesson (1 sentence):"
            )
            try:
                return await llm_call(prompt)
            except Exception:
                pass
        # Heuristic fallback
        if len(response) > 200:
            return f"Answered question about: {query[:50]}"
        return ""

    async def _enforce_limit(self) -> None:
        count = self._conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        if count > self.max_entries:
            excess = count - self.max_entries
            self._conn.execute(
                "DELETE FROM episodes WHERE id IN (SELECT id FROM episodes ORDER BY timestamp ASC LIMIT ?)",
                (excess,),
            )
            self._conn.commit()

    def _row_to_episode(self, row) -> Episode:
        return Episode(
            id=row[0], query=row[1], response=row[2], lesson=row[3],
            confidence=row[4], timestamp=row[5],
            metadata=json.loads(row[6]) if row[6] else {},
        )

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
