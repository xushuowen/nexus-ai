"""Agent discovery and registration system."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """Discovers, registers, and manages specialist agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        logger.info(f"Registered agent: {agent.name}")

    def unregister(self, name: str) -> None:
        if name in self._agents:
            del self._agents[name]

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def find_by_capability(self, capability: AgentCapability) -> list[BaseAgent]:
        return [a for a in self._agents.values() if capability in a.capabilities]

    def rank_for_message(self, message: AgentMessage, context: dict[str, Any]) -> list[tuple[BaseAgent, float]]:
        """Rank all agents by their ability to handle a message."""
        scored = []
        for agent in self._agents.values():
            score = agent.can_handle(message, context)
            if score > 0:
                scored.append((agent, score))
        scored.sort(key=lambda x: (-x[1], -x[0].priority))
        return scored

    def describe_all_for_llm(self) -> str:
        """Get descriptions of all agents for LLM routing."""
        lines = []
        for agent in self._agents.values():
            lines.append(agent.describe_for_llm())
        return "\n".join(lines)

    async def auto_discover(self, agents_dir: Path | None = None) -> None:
        """Auto-discover and register agents from the agents/ directory."""
        if agents_dir is None:
            agents_dir = Path(__file__).resolve().parent.parent / "agents"
        if not agents_dir.exists():
            return
        for py_file in agents_dir.glob("*_agent.py"):
            module_name = f"nexus.agents.{py_file.stem}"
            try:
                mod = importlib.import_module(module_name)
                # Look for a class that extends BaseAgent
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseAgent)
                        and attr is not BaseAgent
                    ):
                        agent = attr()
                        await agent.initialize()
                        self.register(agent)
            except Exception as e:
                logger.warning(f"Failed to load agent from {py_file}: {e}")

    async def shutdown_all(self) -> None:
        for agent in self._agents.values():
            try:
                await agent.shutdown()
            except Exception as e:
                logger.warning(f"Error shutting down {agent.name}: {e}")
        self._agents.clear()
