"""Layer 3c: Knowledge Graph with Hebbian learning weights.
Uses NetworkX + SQLite for lightweight graph storage. Zero token cost."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import networkx as nx

from nexus import config

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """Graph-based knowledge store with Hebbian weight updates.
    Concepts that are used together get stronger connections."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or Path(config.get("memory.sqlite_path", "./data/nexus.db"))
        self.learning_rate: float = config.get("memory.hebbian_learning_rate", 0.1)
        self.graph = nx.DiGraph()
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                category TEXT DEFAULT '',
                properties TEXT DEFAULT '{}',
                activation REAL DEFAULT 1.0,
                created_at REAL NOT NULL,
                last_accessed REAL NOT NULL
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS kg_edges (
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT DEFAULT '',
                weight REAL DEFAULT 1.0,
                co_activation_count INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                PRIMARY KEY (source, target, relation),
                FOREIGN KEY (source) REFERENCES kg_nodes(id),
                FOREIGN KEY (target) REFERENCES kg_nodes(id)
            )
        """)
        self._conn.commit()
        await self._load_graph()

    async def _load_graph(self) -> None:
        """Load graph from SQLite into NetworkX."""
        self.graph.clear()
        for row in self._conn.execute("SELECT id, label, category, properties, activation FROM kg_nodes").fetchall():
            self.graph.add_node(row[0], label=row[1], category=row[2],
                                properties=json.loads(row[3]), activation=row[4])
        for row in self._conn.execute("SELECT source, target, relation, weight, co_activation_count FROM kg_edges").fetchall():
            self.graph.add_edge(row[0], row[1], relation=row[2], weight=row[3], co_activations=row[4])

    async def add_concept(self, concept_id: str, label: str, category: str = "", properties: dict | None = None) -> None:
        """Add a concept node to the knowledge graph."""
        now = time.time()
        props = json.dumps(properties or {})
        self._conn.execute(
            "INSERT OR REPLACE INTO kg_nodes (id, label, category, properties, activation, created_at, last_accessed) "
            "VALUES (?, ?, ?, ?, 1.0, ?, ?)",
            (concept_id, label, category, props, now, now),
        )
        self._conn.commit()
        self.graph.add_node(concept_id, label=label, category=category,
                            properties=properties or {}, activation=1.0)

    async def add_relation(self, source: str, target: str, relation: str = "related_to", weight: float = 1.0) -> None:
        """Add a directed edge between concepts."""
        now = time.time()
        self._conn.execute(
            "INSERT OR REPLACE INTO kg_edges (source, target, relation, weight, co_activation_count, created_at) "
            "VALUES (?, ?, ?, ?, 0, ?)",
            (source, target, relation, weight, now),
        )
        self._conn.commit()
        self.graph.add_edge(source, target, relation=relation, weight=weight, co_activations=0)

    async def hebbian_update(self, concepts: list[str]) -> None:
        """Hebbian learning: strengthen connections between co-activated concepts.
        'Neurons that fire together wire together.' Free operation."""
        for i, c1 in enumerate(concepts):
            for c2 in concepts[i + 1:]:
                if self.graph.has_edge(c1, c2):
                    data = self.graph[c1][c2]
                    data["weight"] = min(10.0, data["weight"] + self.learning_rate)
                    data["co_activations"] = data.get("co_activations", 0) + 1
                    self._conn.execute(
                        "UPDATE kg_edges SET weight = ?, co_activation_count = co_activation_count + 1 "
                        "WHERE source = ? AND target = ?",
                        (data["weight"], c1, c2),
                    )
                elif c1 in self.graph and c2 in self.graph:
                    await self.add_relation(c1, c2, "co_activated", self.learning_rate)
        self._conn.commit()

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for concepts matching query."""
        query_lower = query.lower()
        results = []
        for node_id, data in self.graph.nodes(data=True):
            label = data.get("label", "").lower()
            if query_lower in label or query_lower in node_id.lower():
                results.append({
                    "id": node_id,
                    "label": data.get("label", ""),
                    "category": data.get("category", ""),
                    "activation": data.get("activation", 1.0),
                    "connections": list(self.graph.successors(node_id)),
                })
        results.sort(key=lambda x: -x["activation"])
        return results[:limit]

    async def get_neighbors(self, concept_id: str, depth: int = 1) -> dict[str, Any]:
        """Get concept and its neighbors up to given depth."""
        if concept_id not in self.graph:
            return {}
        subgraph = nx.ego_graph(self.graph, concept_id, radius=depth)
        nodes = {n: dict(subgraph.nodes[n]) for n in subgraph.nodes}
        edges = [(u, v, dict(d)) for u, v, d in subgraph.edges(data=True)]
        return {"nodes": nodes, "edges": edges}

    async def decay(self, rate: float | None = None) -> int:
        """Apply decay to all node activations. Returns count of removed nodes."""
        r = rate or config.get("memory.semantic_decay_rate", 0.01)
        removed = 0
        to_remove = []
        for node_id, data in self.graph.nodes(data=True):
            data["activation"] = data.get("activation", 1.0) * (1.0 - r)
            if data["activation"] < 0.01:
                to_remove.append(node_id)
        for node_id in to_remove:
            self.graph.remove_node(node_id)
            self._conn.execute("DELETE FROM kg_nodes WHERE id = ?", (node_id,))
            self._conn.execute("DELETE FROM kg_edges WHERE source = ? OR target = ?", (node_id, node_id))
            removed += 1
        if to_remove:
            self._conn.commit()
        return removed

    async def get_random_pair(self) -> tuple[str, str] | None:
        """Get a random pair of concepts for the novelty engine."""
        import random
        nodes = list(self.graph.nodes)
        if len(nodes) < 2:
            return None
        return tuple(random.sample(nodes, 2))

    async def find_contradictions(self) -> list[tuple[str, str, str]]:
        """Find potential contradictions in the graph (local, free)."""
        contradictions = []
        for node in self.graph.nodes:
            neighbors = list(self.graph.successors(node))
            for i, n1 in enumerate(neighbors):
                for n2 in neighbors[i + 1:]:
                    e1 = self.graph[node][n1]
                    e2 = self.graph[node][n2]
                    if e1.get("relation") == "is" and e2.get("relation") == "is_not":
                        contradictions.append((node, n1, n2))
        return contradictions

    async def close(self) -> None:
        if self._conn:
            self._conn.close()
