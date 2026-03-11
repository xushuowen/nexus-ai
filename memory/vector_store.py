"""Layer 3b: Gemini Embedding API vector search stored in SQLite.

Replaces ChromaDB + sentence-transformers:
- No extra dependencies (google-genai already required)
- Works on Cloud Run without chromadb
- Higher accuracy: MTEB 68.17 vs sentence-transformers ~65
- Uses RETRIEVAL_QUERY / RETRIEVAL_DOCUMENT task types for best results
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768  # MRL truncated dimension — saves storage, minimal quality loss


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class VectorStore:
    """Gemini Embedding API semantic search with SQLite persistence.

    Stores embeddings as JSON in SQLite. On search, embeds the query
    and computes cosine similarity against all stored vectors — fast
    enough for a personal assistant's memory size.
    """

    def __init__(self, persist_path: Path | None = None) -> None:
        data_dir = Path(config.get("memory.vector_store_path", "./data/chroma")).parent
        self._db_path = data_dir / "gemini_vectors.db"
        self._conn: sqlite3.Connection | None = None
        self._client = None
        self._available = False

    async def initialize(self) -> None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("No Gemini API key — VectorStore (semantic search) disabled.")
            return
        try:
            from google import genai
            self._client = genai.Client(api_key=api_key)
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id        TEXT PRIMARY KEY,
                    content   TEXT NOT NULL,
                    embedding TEXT NOT NULL,
                    metadata  TEXT NOT NULL DEFAULT '{}',
                    timestamp REAL NOT NULL
                )
            """)
            self._conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON vectors(timestamp)")
            self._conn.commit()
            count = self._conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
            self._available = True
            logger.info("VectorStore (Gemini Embedding) initialised — %d vectors in DB", count)
        except Exception as e:
            logger.warning("VectorStore init failed: %s — semantic search disabled.", e)
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def _embed_sync(self, text: str, task_type: str) -> list[float] | None:
        """Synchronous embedding call — run via executor to avoid blocking."""
        try:
            from google.genai import types
            result = self._client.models.embed_content(
                model=EMBED_MODEL,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBED_DIM,
                ),
            )
            return list(result.embeddings[0].values)
        except Exception as e:
            logger.warning("Gemini embed error: %s", e)
            return None

    async def _embed(self, text: str, task_type: str) -> list[float] | None:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._embed_sync, text, task_type)

    async def store(
        self,
        text: str,
        doc_id: str | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        """Embed text and persist to SQLite."""
        if not self._available:
            return None
        embedding = await self._embed(text, "RETRIEVAL_DOCUMENT")
        if embedding is None:
            return None
        doc_id = doc_id or str(uuid.uuid4())
        meta = metadata or {}
        try:
            self._conn.execute(
                "INSERT OR REPLACE INTO vectors (id, content, embedding, metadata, timestamp)"
                " VALUES (?, ?, ?, ?, ?)",
                (doc_id, text, json.dumps(embedding), json.dumps(meta), time.time()),
            )
            self._conn.commit()
            return doc_id
        except Exception as e:
            logger.warning("Vector store write error: %s", e)
            return None

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Embed query and return top-k most similar documents."""
        if not self._available:
            return []

        q_vec = await self._embed(query, "RETRIEVAL_QUERY")
        if q_vec is None:
            return []

        try:
            rows = self._conn.execute(
                "SELECT id, content, embedding, metadata, timestamp FROM vectors"
            ).fetchall()
        except Exception as e:
            logger.warning("Vector search fetch error: %s", e)
            return []

        scored: list[dict] = []
        for row_id, content, emb_json, meta_json, ts in rows:
            try:
                score = _cosine_similarity(q_vec, json.loads(emb_json))
                scored.append({
                    "content": content,
                    "id": row_id,
                    "distance": 1.0 - score,   # lower = more similar
                    "metadata": json.loads(meta_json),
                    "timestamp": ts,
                })
            except Exception:
                continue

        scored.sort(key=lambda x: x["distance"])
        return scored[:top_k]

    async def delete(self, doc_id: str) -> None:
        if self._available and self._conn:
            try:
                self._conn.execute("DELETE FROM vectors WHERE id = ?", (doc_id,))
                self._conn.commit()
            except Exception:
                pass

    async def count(self) -> int:
        if not self._available or not self._conn:
            return 0
        try:
            return self._conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
        except Exception:
            return 0

    async def close(self) -> None:
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
