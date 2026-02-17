"""Local-first Novelty Engine - concept blending, analogy, and contradiction detection.
Most operations are free (local graph operations). LLM only for final descriptions."""

from __future__ import annotations

import logging
import random
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from nexus.memory.knowledge_graph import KnowledgeGraph
    from nexus.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class ConceptBlender:
    """Blends concepts from the knowledge graph to find novel combinations.
    Graph operations are free; LLM only for describing the blend."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self.kg = kg

    async def find_blendable_pairs(self, n: int = 5) -> list[tuple[str, str, float]]:
        """Find pairs of concepts that might yield interesting blends.
        Uses graph distance as a creativity metric (further = more creative).
        Free operation."""
        import networkx as nx

        nodes = list(self.kg.graph.nodes)
        if len(nodes) < 2:
            return []

        pairs = []
        attempts = min(n * 3, len(nodes) * 2)
        for _ in range(attempts):
            a, b = random.sample(nodes, 2)
            try:
                dist = nx.shortest_path_length(self.kg.graph.to_undirected(), a, b)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                dist = 10  # Disconnected = very creative
            # Sweet spot: not too close (boring), not too far (nonsensical)
            if 2 <= dist <= 6:
                pairs.append((a, b, dist))
            if len(pairs) >= n:
                break
        pairs.sort(key=lambda x: -x[2])  # Most distant first
        return pairs

    async def describe_blend(self, concept_a: str, concept_b: str, llm: LLMProvider) -> str:
        """Use LLM to describe a novel concept blend."""
        prompt = (
            f"Imagine combining the concepts of '{concept_a}' and '{concept_b}' "
            f"into something new. What could this combination look like? "
            f"Be creative but practical. (2-3 sentences)"
        )
        return await llm.complete(prompt, source="novelty", task_type="simple_tasks")


class AnalogyEngine:
    """Finds structural analogies in the knowledge graph.
    All graph comparisons are free; LLM only for narrating the analogy."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self.kg = kg

    async def find_analogies(self, concept: str, limit: int = 3) -> list[dict[str, Any]]:
        """Find concepts with similar graph structure (free operation)."""
        if concept not in self.kg.graph:
            return []

        source_neighbors = set(self.kg.graph.successors(concept))
        source_in = set(self.kg.graph.predecessors(concept))

        analogies = []
        for node in self.kg.graph.nodes:
            if node == concept:
                continue
            node_neighbors = set(self.kg.graph.successors(node))
            node_in = set(self.kg.graph.predecessors(node))

            # Jaccard similarity of neighborhood structure
            out_sim = len(source_neighbors & node_neighbors) / max(1, len(source_neighbors | node_neighbors))
            in_sim = len(source_in & node_in) / max(1, len(source_in | node_in))
            structural_sim = (out_sim + in_sim) / 2

            if structural_sim > 0.2:
                analogies.append({
                    "concept": node,
                    "similarity": structural_sim,
                    "shared_relations": list(source_neighbors & node_neighbors),
                })

        analogies.sort(key=lambda x: -x["similarity"])
        return analogies[:limit]

    async def describe_analogy(self, source: str, target: str, shared: list[str], llm: LLMProvider) -> str:
        """Use LLM to describe the analogy."""
        shared_str = ", ".join(shared[:5]) if shared else "structural patterns"
        prompt = (
            f"'{source}' is analogous to '{target}' because they share: {shared_str}. "
            f"Explain this analogy in a way that provides insight. (2-3 sentences)"
        )
        return await llm.complete(prompt, source="novelty", task_type="simple_tasks")


class ContradictionDetector:
    """Detects contradictions in the knowledge graph. All local operations."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self.kg = kg
        self._accumulated: list[tuple] = []

    async def scan(self) -> list[dict[str, Any]]:
        """Scan for contradictions in the knowledge graph (free)."""
        contradictions = []

        for node in self.kg.graph.nodes:
            edges = list(self.kg.graph.out_edges(node, data=True))
            # Check for conflicting "is" and "is_not" relations
            is_targets = {}
            for _, target, data in edges:
                rel = data.get("relation", "")
                if rel.startswith("is"):
                    is_targets.setdefault(rel, []).append(target)

            if "is" in is_targets and "is_not" in is_targets:
                overlap = set(is_targets["is"]) & set(is_targets["is_not"])
                if overlap:
                    contradictions.append({
                        "node": node,
                        "type": "is_conflict",
                        "details": f"{node} both is and is_not {overlap}",
                    })

        self._accumulated.extend([(c["node"], c["type"]) for c in contradictions])
        return contradictions

    async def analyze_batch(self, contradictions: list[dict], llm: LLMProvider) -> str:
        """Use LLM to analyze accumulated contradictions (budget-controlled)."""
        if not contradictions:
            return "No contradictions found."
        desc = "\n".join(c.get("details", str(c)) for c in contradictions[:5])
        prompt = (
            f"Analyze these knowledge contradictions and suggest resolutions:\n{desc}\n"
            f"Be concise."
        )
        return await llm.complete(prompt, source="novelty", task_type="simple_tasks")


class NoveltyEngine:
    """Orchestrates all novelty-finding components."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self.blender = ConceptBlender(kg)
        self.analogy = AnalogyEngine(kg)
        self.contradiction = ContradictionDetector(kg)

    async def explore(self, llm: LLMProvider | None = None) -> dict[str, Any]:
        """Run a novelty exploration cycle."""
        results: dict[str, Any] = {}

        # Free operations
        pairs = await self.blender.find_blendable_pairs(3)
        results["blendable_pairs"] = [(p[0], p[1]) for p in pairs]

        contradictions = await self.contradiction.scan()
        results["contradictions"] = len(contradictions)

        # LLM operations (only if available)
        if llm and pairs:
            best_pair = pairs[0]
            blend_desc = await self.blender.describe_blend(best_pair[0], best_pair[1], llm)
            results["blend_description"] = blend_desc

        return results
