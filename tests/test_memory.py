"""Tests for the 4-layer memory system."""

import asyncio
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def config_mock(temp_dir):
    cfg = {
        "memory": {
            "working_memory_slots": 7,
            "episodic_max_entries": 100,
            "semantic_decay_rate": 0.01,
            "hebbian_learning_rate": 0.1,
            "consolidation_interval_minutes": 30,
            "vector_store_path": str(temp_dir / "chroma"),
            "sqlite_path": str(temp_dir / "test.db"),
        }
    }
    with patch("nexus.config.load_config", return_value=cfg), \
         patch("nexus.config.get", side_effect=lambda k, d=None: {
             "memory.sqlite_path": str(temp_dir / "test.db"),
             "memory.episodic_max_entries": 100,
             "memory.vector_store_path": str(temp_dir / "chroma"),
             "memory.hebbian_learning_rate": 0.1,
             "memory.semantic_decay_rate": 0.01,
         }.get(k, d)), \
         patch("nexus.config.data_dir", return_value=temp_dir):
        yield cfg


# ── Working Memory Tests ──
class TestWorkingMemory:
    def test_store_and_retrieve(self):
        from nexus.memory.working_memory import WorkingMemory
        wm = WorkingMemory(max_slots=3)
        wm.store("key1", "value1")
        assert wm.retrieve("key1") == "value1"

    def test_eviction(self):
        from nexus.memory.working_memory import WorkingMemory
        wm = WorkingMemory(max_slots=2)
        wm.store("a", "1", attention=0.5)
        wm.store("b", "2", attention=0.8)
        wm.store("c", "3", attention=0.9)  # should evict "a"
        assert wm.retrieve("a") is None
        assert wm.retrieve("b") == "2"

    def test_search(self):
        from nexus.memory.working_memory import WorkingMemory
        wm = WorkingMemory()
        wm.store("q1", "quantum physics explanation")
        wm.store("q2", "quantum computing basics")
        results = wm.search("quantum")
        assert len(results) == 2

    def test_decay(self):
        from nexus.memory.working_memory import WorkingMemory
        wm = WorkingMemory()
        wm.store("x", "value", attention=0.1)
        wm.decay_all(rate=0.95)  # Heavy decay
        assert wm.size == 0  # Should be evicted


# ── Episodic Memory Tests ──
class TestEpisodicMemory:
    @pytest.mark.asyncio
    async def test_store_and_search(self, config_mock, temp_dir):
        from nexus.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory(db_path=temp_dir / "test.db")
        await em.initialize()
        await em.store("What is AI?", "AI is artificial intelligence.", confidence=0.9)
        results = await em.search("AI")
        assert len(results) >= 1
        assert results[0].confidence == 0.9
        await em.close()

    @pytest.mark.asyncio
    async def test_recent(self, config_mock, temp_dir):
        from nexus.memory.episodic_memory import EpisodicMemory
        em = EpisodicMemory(db_path=temp_dir / "test.db")
        await em.initialize()
        await em.store("Q1", "A1")
        await em.store("Q2", "A2")
        recent = await em.get_recent(limit=5)
        assert len(recent) == 2
        await em.close()


# ── Knowledge Graph Tests ──
class TestKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_add_and_search(self, config_mock, temp_dir):
        from nexus.memory.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(db_path=temp_dir / "test.db")
        await kg.initialize()
        await kg.add_concept("python", "Python", category="language")
        results = await kg.search("Python")
        assert len(results) >= 1
        await kg.close()

    @pytest.mark.asyncio
    async def test_hebbian_update(self, config_mock, temp_dir):
        from nexus.memory.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph(db_path=temp_dir / "test.db")
        await kg.initialize()
        await kg.add_concept("ai", "AI")
        await kg.add_concept("ml", "Machine Learning")
        await kg.add_relation("ai", "ml", "includes")
        await kg.hebbian_update(["ai", "ml"])
        edge = kg.graph["ai"]["ml"]
        assert edge["weight"] > 1.0  # Strengthened
        await kg.close()


# ── Procedural Memory Tests ──
class TestProceduralMemory:
    @pytest.mark.asyncio
    async def test_store_and_lookup(self, config_mock, temp_dir):
        from nexus.memory.procedural_memory import ProceduralMemory
        pm = ProceduralMemory(db_path=temp_dir / "test.db")
        await pm.initialize()
        await pm.store("How to sort a list?", "Use sorted() in Python.")
        result = await pm.lookup("How to sort a list?")
        assert result is not None
        assert "sorted" in result
        await pm.close()

    @pytest.mark.asyncio
    async def test_lookup_miss(self, config_mock, temp_dir):
        from nexus.memory.procedural_memory import ProceduralMemory
        pm = ProceduralMemory(db_path=temp_dir / "test.db")
        await pm.initialize()
        result = await pm.lookup("completely unrelated query xyz")
        assert result is None
        await pm.close()
