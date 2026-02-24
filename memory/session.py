"""Conversation session history manager."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    """Manages conversation sessions with persistence."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(config.get("memory.sqlite_path", "./data/nexus.db"))
        self._conn: sqlite3.Connection | None = None
        self._sessions: dict[str, list[Message]] = {}

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_sess_id ON sessions(session_id, timestamp)")
        self._conn.commit()

    async def add_message(self, session_id: str, role: str, content: str, metadata: dict | None = None) -> None:
        msg = Message(role=role, content=content, metadata=metadata or {})
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(msg)

        self._conn.execute(
            "INSERT INTO sessions (session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, msg.timestamp, json.dumps(msg.metadata)),
        )
        self._conn.commit()

    async def get_history(self, session_id: str, limit: int = 20) -> list[Message]:
        """Get recent conversation history."""
        if session_id in self._sessions:
            return self._sessions[session_id][-limit:]

        rows = self._conn.execute(
            "SELECT role, content, timestamp, metadata FROM sessions "
            "WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        messages = [
            Message(role=r[0], content=r[1], timestamp=r[2],
                    metadata=json.loads(r[3]) if r[3] else {})
            for r in reversed(rows)
        ]
        self._sessions[session_id] = messages
        return messages

    async def get_context_for_prompt(self, session_id: str, max_messages: int = 10) -> list[dict[str, str]]:
        """Get conversation formatted for LLM prompt."""
        history = await self.get_history(session_id, limit=max_messages)
        return [{"role": m.role, "content": m.content} for m in history]

    async def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._conn.commit()

    async def prune_old_messages(self, keep_days: int = 30) -> int:
        """Delete session messages older than keep_days. Returns number deleted.

        Call this on startup or periodically to keep the DB from growing forever.
        """
        cutoff = time.time() - (keep_days * 86400)
        result = self._conn.execute(
            "DELETE FROM sessions WHERE timestamp < ?", (cutoff,)
        )
        self._conn.commit()
        deleted = result.rowcount
        if deleted:
            # Evict stale sessions from the in-memory cache too
            self._sessions.clear()
            logger.info(f"Session pruner: removed {deleted} messages older than {keep_days} days")
        return deleted

    async def prune_session(self, session_id: str, keep_last: int = 200) -> None:
        """Keep only the most recent keep_last messages for one session.

        Prevents a single long-running session from consuming unbounded space.
        """
        rows = self._conn.execute(
            "SELECT id FROM sessions WHERE session_id = ? ORDER BY timestamp DESC LIMIT -1 OFFSET ?",
            (session_id, keep_last),
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            self._conn.execute(
                f"DELETE FROM sessions WHERE id IN ({','.join('?' * len(ids))})", ids
            )
            self._conn.commit()
            self._sessions.pop(session_id, None)  # invalidate cache

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
