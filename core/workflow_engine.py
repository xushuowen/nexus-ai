"""DAG-based workflow execution engine."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowNode:
    """A single step in a workflow DAG."""
    id: str
    name: str
    handler: Callable[..., Awaitable[Any]]
    depends_on: list[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class WorkflowEngine:
    """Executes workflows defined as DAGs with parallel node execution."""

    def __init__(self) -> None:
        self._nodes: dict[str, WorkflowNode] = {}
        self._on_node_complete: list[Callable] = []

    def add_node(self, node: WorkflowNode) -> None:
        self._nodes[node.id] = node

    def on_node_complete(self, callback: Callable) -> None:
        self._on_node_complete.append(callback)

    def _get_ready_nodes(self) -> list[WorkflowNode]:
        """Find nodes whose dependencies are all completed."""
        ready = []
        for node in self._nodes.values():
            if node.status != NodeStatus.PENDING:
                continue
            deps_met = all(
                self._nodes[dep].status == NodeStatus.COMPLETED
                for dep in node.depends_on
                if dep in self._nodes
            )
            deps_failed = any(
                self._nodes[dep].status == NodeStatus.FAILED
                for dep in node.depends_on
                if dep in self._nodes
            )
            if deps_failed:
                node.status = NodeStatus.SKIPPED
            elif deps_met:
                ready.append(node)
        return ready

    async def execute(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the workflow, running independent nodes in parallel."""
        ctx = context or {}
        results: dict[str, Any] = {}

        while True:
            ready = self._get_ready_nodes()
            if not ready:
                # Check if all done
                pending = [n for n in self._nodes.values() if n.status == NodeStatus.PENDING]
                if not pending:
                    break
                running = [n for n in self._nodes.values() if n.status == NodeStatus.RUNNING]
                if not running:
                    break
                await asyncio.sleep(0.05)
                continue

            tasks = []
            for node in ready:
                node.status = NodeStatus.RUNNING
                tasks.append(self._run_node(node, ctx, results))

            await asyncio.gather(*tasks)

        return results

    async def _run_node(
        self, node: WorkflowNode, context: dict[str, Any], results: dict[str, Any]
    ) -> None:
        try:
            dep_results = {d: results.get(d) for d in node.depends_on}
            node.result = await node.handler(context=context, dep_results=dep_results, **node.metadata)
            node.status = NodeStatus.COMPLETED
            results[node.id] = node.result
            for cb in self._on_node_complete:
                try:
                    await cb(node)
                except Exception:
                    pass
        except Exception as e:
            node.status = NodeStatus.FAILED
            node.error = str(e)
            logger.error(f"Workflow node '{node.id}' failed: {e}")

    def reset(self) -> None:
        for node in self._nodes.values():
            node.status = NodeStatus.PENDING
            node.result = None
            node.error = None

    def get_status(self) -> dict[str, str]:
        return {nid: node.status.value for nid, node in self._nodes.items()}
