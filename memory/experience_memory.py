"""Experience Memory — tracks user preferences and feedback for adaptive responses.

Inspired by Project Golem's preference learning. Records:
- Positive feedback (thumbs up, 讚, good)
- Negative feedback (不好, 重新, bad)
- Rejection patterns (user re-asks or corrects)
- Learned preferences (language, format, style)

This context is injected into prompts to improve future responses.
"""

from __future__ import annotations

import sqlite3
import time
import logging
from pathlib import Path
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)


class ExperienceMemory:
    """Stores and retrieves user experience data for preference learning."""

    def __init__(self) -> None:
        self._db_path = config.data_dir() / "experience.db"
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                response_preview TEXT NOT NULL,
                feedback_type TEXT NOT NULL,
                details TEXT DEFAULT '',
                timestamp REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                updated REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS avoidance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pattern TEXT NOT NULL,
                reason TEXT DEFAULT '',
                count INTEGER DEFAULT 1,
                timestamp REAL NOT NULL
            )
        """)
        self._conn.commit()

    async def record_feedback(
        self, query: str, response: str, feedback: str, details: str = ""
    ) -> None:
        """Record user feedback on a response."""
        feedback_type = self._classify_feedback(feedback)
        self._conn.execute(
            "INSERT INTO feedback (query, response_preview, feedback_type, details, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (query, response[:300], feedback_type, details, time.time()),
        )
        self._conn.commit()

        # Auto-learn from negative feedback
        if feedback_type == "negative":
            await self._learn_from_negative(query, response, details)

        logger.info(f"Experience feedback recorded: {feedback_type}")

    async def record_rejection(self, query: str, response: str) -> None:
        """Record when a user re-asks (implicit rejection)."""
        await self.record_feedback(query, response, "negative", "User re-asked the question")

    async def record_preference(self, key: str, value: str, confidence: float = 0.7) -> None:
        """Store or update a user preference."""
        self._conn.execute(
            "INSERT INTO preferences (key, value, confidence, updated) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=?, confidence=?, updated=?",
            (key, value, confidence, time.time(), value, confidence, time.time()),
        )
        self._conn.commit()

    async def get_preferences(self) -> dict[str, Any]:
        """Get all learned preferences."""
        rows = self._conn.execute(
            "SELECT key, value, confidence FROM preferences ORDER BY confidence DESC"
        ).fetchall()
        return {key: {"value": value, "confidence": conf} for key, value, conf in rows}

    async def get_avoidance_list(self) -> list[dict]:
        """Get patterns to avoid based on negative feedback."""
        rows = self._conn.execute(
            "SELECT pattern, reason, count FROM avoidance ORDER BY count DESC LIMIT 20"
        ).fetchall()
        return [{"pattern": p, "reason": r, "count": c} for p, r, c in rows]

    async def inject_context(self) -> str:
        """Generate preference context string for prompt injection."""
        parts = []

        # Preferences
        prefs = await self.get_preferences()
        if prefs:
            pref_lines = []
            for key, data in list(prefs.items())[:10]:
                pref_lines.append(f"  - {key}: {data['value']}")
            if pref_lines:
                parts.append("User preferences:\n" + "\n".join(pref_lines))

        # Avoidance
        avoidance = await self.get_avoidance_list()
        if avoidance:
            avoid_lines = [f"  - Avoid: {a['pattern']}" for a in avoidance[:5]]
            if avoid_lines:
                parts.append("Things to avoid:\n" + "\n".join(avoid_lines))

        return "\n".join(parts) if parts else ""

    async def get_feedback_stats(self) -> dict[str, int]:
        """Get feedback statistics."""
        rows = self._conn.execute(
            "SELECT feedback_type, COUNT(*) FROM feedback GROUP BY feedback_type"
        ).fetchall()
        return dict(rows)

    def _classify_feedback(self, feedback: str) -> str:
        """Classify feedback text into positive/negative/neutral."""
        text = feedback.lower()
        positive = ["好", "讚", "good", "great", "nice", "correct", "對", "棒", "感謝", "thanks", "👍"]
        negative = ["不好", "錯", "bad", "wrong", "重新", "redo", "不對", "差", "爛", "👎"]

        if any(w in text for w in positive):
            return "positive"
        if any(w in text for w in negative):
            return "negative"
        return "neutral"

    async def _learn_from_negative(self, query: str, response: str, details: str) -> None:
        """Extract avoidance patterns from negative feedback."""
        pattern = f"Response style for: {query[:80]}"
        reason = details if details else "User expressed dissatisfaction"

        # Check if similar pattern exists
        existing = self._conn.execute(
            "SELECT id, count FROM avoidance WHERE pattern = ?", (pattern,)
        ).fetchone()

        if existing:
            self._conn.execute(
                "UPDATE avoidance SET count = count + 1, timestamp = ? WHERE id = ?",
                (time.time(), existing[0]),
            )
        else:
            self._conn.execute(
                "INSERT INTO avoidance (pattern, reason, timestamp) VALUES (?, ?, ?)",
                (pattern, reason, time.time()),
            )
        self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
