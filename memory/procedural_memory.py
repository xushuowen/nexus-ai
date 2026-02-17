"""Layer 4: Procedural Memory - Cache successful reasoning chains for reuse.
In-context Learning replacement for LoRA. Zero token cost for retrieval."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from nexus import config


class ProceduralMemory:
    """Stores successful reasoning chains as reusable procedures.
    Acts as an in-context learning cache: if we've seen a similar question,
    return the cached answer instead of calling the LLM."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(config.get("memory.sqlite_path", "./data/nexus.db"))
        self._conn: sqlite3.Connection | None = None
        self._similarity_threshold = 0.85

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS procedures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query_hash TEXT NOT NULL,
                query_normalized TEXT NOT NULL,
                response TEXT NOT NULL,
                reasoning_chain TEXT DEFAULT '[]',
                success_count INTEGER DEFAULT 1,
                fail_count INTEGER DEFAULT 0,
                confidence REAL DEFAULT 0.8,
                created_at REAL NOT NULL,
                last_used REAL NOT NULL,
                metadata TEXT DEFAULT '{}'
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proc_hash ON procedures(query_hash)
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_proc_conf ON procedures(confidence DESC)
        """)
        self._conn.commit()

    def _normalize_query(self, query: str) -> str:
        """Normalize a query for matching."""
        return " ".join(query.lower().strip().split())

    def _hash_query(self, query: str) -> str:
        normalized = self._normalize_query(query)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    async def store(
        self,
        query: str,
        response: str,
        reasoning_chain: list[str] | None = None,
        confidence: float = 0.8,
        metadata: dict | None = None,
    ) -> int:
        """Cache a successful reasoning chain."""
        qhash = self._hash_query(query)
        normalized = self._normalize_query(query)
        now = time.time()

        # Check if we already have this exact query
        existing = self._conn.execute(
            "SELECT id, success_count FROM procedures WHERE query_hash = ?", (qhash,)
        ).fetchone()

        if existing:
            self._conn.execute(
                "UPDATE procedures SET success_count = success_count + 1, last_used = ?, "
                "confidence = MIN(1.0, confidence + 0.05) WHERE id = ?",
                (now, existing[0]),
            )
            self._conn.commit()
            return existing[0]

        cursor = self._conn.execute(
            "INSERT INTO procedures (query_hash, query_normalized, response, reasoning_chain, "
            "confidence, created_at, last_used, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (qhash, normalized, response, json.dumps(reasoning_chain or []),
             confidence, now, now, json.dumps(metadata or {})),
        )
        self._conn.commit()
        return cursor.lastrowid

    async def lookup(self, query: str) -> str | None:
        """Look up a cached response for a query. Returns None if no match."""
        qhash = self._hash_query(query)
        row = self._conn.execute(
            "SELECT id, response, confidence FROM procedures WHERE query_hash = ? AND confidence >= 0.5",
            (qhash,),
        ).fetchone()
        if row:
            self._conn.execute(
                "UPDATE procedures SET last_used = ?, success_count = success_count + 1 WHERE id = ?",
                (time.time(), row[0]),
            )
            self._conn.commit()
            return row[1]
        return None

    async def get_similar_procedures(self, query: str, limit: int = 3) -> list[dict[str, Any]]:
        """Get similar cached procedures for in-context learning prompt injection."""
        normalized = self._normalize_query(query)
        words = set(normalized.split())
        if not words:
            return []

        # Keyword overlap search
        all_rows = self._conn.execute(
            "SELECT id, query_normalized, response, reasoning_chain, confidence "
            "FROM procedures WHERE confidence >= 0.5 ORDER BY confidence DESC LIMIT 100"
        ).fetchall()

        scored = []
        for row in all_rows:
            stored_words = set(row[1].split())
            if not stored_words:
                continue
            overlap = len(words & stored_words) / max(len(words | stored_words), 1)
            if overlap > 0.3:
                scored.append({
                    "id": row[0],
                    "query": row[1],
                    "response": row[2],
                    "reasoning_chain": json.loads(row[3]) if row[3] else [],
                    "confidence": row[4],
                    "similarity": overlap,
                })
        scored.sort(key=lambda x: -x["similarity"])
        return scored[:limit]

    async def mark_failure(self, query: str) -> None:
        """Mark a cached procedure as having failed (reduces confidence)."""
        qhash = self._hash_query(query)
        self._conn.execute(
            "UPDATE procedures SET fail_count = fail_count + 1, "
            "confidence = MAX(0.0, confidence - 0.1) WHERE query_hash = ?",
            (qhash,),
        )
        self._conn.commit()

    async def get_top_procedures(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get top-performing procedures for in-context learning prefix."""
        rows = self._conn.execute(
            "SELECT query_normalized, response, reasoning_chain, confidence "
            "FROM procedures WHERE confidence >= 0.7 ORDER BY success_count DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"query": r[0], "response": r[1],
             "chain": json.loads(r[2]) if r[2] else [], "confidence": r[3]}
            for r in rows
        ]

    async def cleanup(self, min_confidence: float = 0.2) -> int:
        """Remove low-confidence procedures."""
        cursor = self._conn.execute(
            "DELETE FROM procedures WHERE confidence < ?", (min_confidence,)
        )
        self._conn.commit()
        return cursor.rowcount

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
