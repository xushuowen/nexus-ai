"""Layer 3a: SQLite FTS5 full-text search for semantic memory."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from nexus import config


class FTSStore:
    """SQLite FTS5-based keyword search for knowledge retrieval.
    Zero token cost - all local computation."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(config.get("memory.sqlite_path", "./data/nexus.db"))
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        # Create FTS5 virtual table
        self._conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                title, content, category, tags,
                tokenize='unicode61'
            )
        """)
        # Metadata table for non-FTS data
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_meta (
                rowid INTEGER PRIMARY KEY,
                source TEXT DEFAULT '',
                timestamp REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.commit()

    async def store(
        self,
        title: str,
        content: str,
        category: str = "",
        tags: str = "",
        source: str = "",
        metadata: dict | None = None,
    ) -> int:
        """Store a knowledge entry with full-text indexing."""
        cursor = self._conn.execute(
            "INSERT INTO knowledge_fts (title, content, category, tags) VALUES (?, ?, ?, ?)",
            (title, content, category, tags),
        )
        rowid = cursor.lastrowid
        self._conn.execute(
            "INSERT INTO knowledge_meta (rowid, source, timestamp, metadata) VALUES (?, ?, ?, ?)",
            (rowid, source, time.time(), json.dumps(metadata or {})),
        )
        self._conn.commit()
        return rowid

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search using FTS5 ranking."""
        try:
            rows = self._conn.execute(
                """SELECT f.rowid, f.title, f.content, f.category, f.tags,
                          m.source, m.timestamp, rank
                   FROM knowledge_fts f
                   LEFT JOIN knowledge_meta m ON f.rowid = m.rowid
                   WHERE knowledge_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            # FTS match failed (bad query syntax), fall back to LIKE
            rows = self._conn.execute(
                """SELECT f.rowid, f.title, f.content, f.category, f.tags,
                          m.source, m.timestamp, 0 as rank
                   FROM knowledge_fts f
                   LEFT JOIN knowledge_meta m ON f.rowid = m.rowid
                   WHERE f.content LIKE ?
                   ORDER BY m.timestamp DESC
                   LIMIT ?""",
                (f"%{query}%", limit),
            ).fetchall()

        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "category": row[3],
                "tags": row[4],
                "source": row[5],
                "timestamp": row[6],
                "score": -row[7] if row[7] else 0,  # FTS5 rank is negative
            })
            # Update access count
            self._conn.execute(
                "UPDATE knowledge_meta SET access_count = access_count + 1 WHERE rowid = ?",
                (row[0],),
            )
        self._conn.commit()
        return results

    async def delete(self, rowid: int) -> None:
        self._conn.execute("DELETE FROM knowledge_fts WHERE rowid = ?", (rowid,))
        self._conn.execute("DELETE FROM knowledge_meta WHERE rowid = ?", (rowid,))
        self._conn.commit()

    async def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM knowledge_fts").fetchone()[0]

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
