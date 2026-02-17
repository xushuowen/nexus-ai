"""Layer 1: Working Memory - Dynamic attention routing for current conversation.
Zero token cost - pure local computation."""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemorySlot:
    """A single working memory slot with attention weight."""
    key: str
    content: Any
    attention_weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class WorkingMemory:
    """Miller's 7±2 working memory model with dynamic attention routing.
    All operations are local (0 token cost)."""

    def __init__(self, max_slots: int = 7) -> None:
        self.max_slots = max_slots
        self._slots: OrderedDict[str, MemorySlot] = OrderedDict()

    def store(self, key: str, content: Any, attention: float = 1.0) -> None:
        """Store item in working memory. Evicts lowest-attention if full."""
        if key in self._slots:
            slot = self._slots[key]
            slot.content = content
            slot.attention_weight = attention
            slot.access_count += 1
            slot.last_accessed = time.time()
            self._slots.move_to_end(key)
            return

        if len(self._slots) >= self.max_slots:
            self._evict_lowest()

        self._slots[key] = MemorySlot(
            key=key, content=content, attention_weight=attention
        )

    def retrieve(self, key: str) -> Any | None:
        """Retrieve and boost attention for accessed item."""
        slot = self._slots.get(key)
        if slot is None:
            return None
        slot.access_count += 1
        slot.last_accessed = time.time()
        slot.attention_weight = min(1.0, slot.attention_weight + 0.1)
        self._slots.move_to_end(key)
        return slot.content

    def search(self, query: str) -> list[tuple[str, Any, float]]:
        """Simple keyword search across working memory slots.
        Returns (key, content, attention) tuples sorted by relevance."""
        query_lower = query.lower()
        results = []
        for slot in self._slots.values():
            content_str = str(slot.content).lower()
            if query_lower in content_str or any(w in content_str for w in query_lower.split()):
                results.append((slot.key, slot.content, slot.attention_weight))
        results.sort(key=lambda x: -x[2])
        return results

    def get_context_window(self) -> list[dict[str, Any]]:
        """Get all working memory contents sorted by attention for prompt injection."""
        items = []
        for slot in sorted(self._slots.values(), key=lambda s: -s.attention_weight):
            items.append({
                "key": slot.key,
                "content": slot.content,
                "attention": slot.attention_weight,
            })
        return items

    def decay_all(self, rate: float = 0.05) -> None:
        """Apply decay to all slots (called periodically). Free operation."""
        to_remove = []
        for key, slot in self._slots.items():
            slot.attention_weight *= (1.0 - rate)
            if slot.attention_weight < 0.01:
                to_remove.append(key)
        for key in to_remove:
            del self._slots[key]

    def _evict_lowest(self) -> None:
        """Remove the slot with lowest attention weight."""
        if not self._slots:
            return
        min_key = min(self._slots, key=lambda k: self._slots[k].attention_weight)
        del self._slots[min_key]

    def clear(self) -> None:
        self._slots.clear()

    @property
    def size(self) -> int:
        return len(self._slots)

    def get_summary(self) -> dict[str, float]:
        """Get attention weights for monitoring."""
        return {k: v.attention_weight for k, v in self._slots.items()}
