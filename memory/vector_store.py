"""Layer 3b: ChromaDB CPU-mode vector search for semantic similarity."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-based vector search running in CPU-only mode.
    Zero token cost - uses local sentence-transformers for embeddings."""

    def __init__(self, persist_path: Path | None = None) -> None:
        self.persist_path = persist_path or Path(config.get("memory.vector_store_path", "./data/chroma"))
        self._client = None
        self._collection = None
        self._available = False

    async def initialize(self) -> None:
        try:
            import chromadb
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.persist_path))
            self._collection = self._client.get_or_create_collection(
                name="nexus_memory",
                metadata={"hnsw:space": "cosine"},
            )
            self._available = True
            logger.info("VectorStore initialized with ChromaDB")
        except ImportError:
            logger.warning("ChromaDB not installed. Vector search disabled.")
            self._available = False
        except Exception as e:
            logger.warning(f"VectorStore init failed: {e}. Vector search disabled.")
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    async def store(
        self,
        text: str,
        doc_id: str | None = None,
        metadata: dict | None = None,
    ) -> str | None:
        """Store text with auto-generated embeddings."""
        if not self._available:
            return None
        import uuid
        doc_id = doc_id or str(uuid.uuid4())
        meta = metadata or {}
        meta["timestamp"] = time.time()
        try:
            self._collection.add(
                documents=[text],
                ids=[doc_id],
                metadatas=[meta],
            )
            return doc_id
        except Exception as e:
            logger.warning(f"Vector store error: {e}")
            return None

    async def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic similarity search."""
        if not self._available:
            return []
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
            )
            items = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    items.append({
                        "content": doc,
                        "id": results["ids"][0][i] if results["ids"] else "",
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    })
            return items
        except Exception as e:
            logger.warning(f"Vector search error: {e}")
            return []

    async def delete(self, doc_id: str) -> None:
        if self._available:
            try:
                self._collection.delete(ids=[doc_id])
            except Exception:
                pass

    async def count(self) -> int:
        if not self._available:
            return 0
        return self._collection.count()

    async def close(self) -> None:
        pass  # ChromaDB PersistentClient handles cleanup
