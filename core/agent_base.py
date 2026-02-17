"""Base agent class for all specialist agents."""

from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator


class AgentCapability(str, Enum):
    CODE = "code"
    RESEARCH = "research"
    KNOWLEDGE = "knowledge"
    REASONING = "reasoning"
    FILE = "file"
    WEB = "web"
    SHELL = "shell"
    VISION = "vision"
    OPTIMIZATION = "optimization"


@dataclass
class AgentResult:
    """Result returned by an agent after processing."""
    content: str
    confidence: float = 0.5
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    source_agent: str = ""
    reasoning_trace: list[str] = field(default_factory=list)


@dataclass
class AgentMessage:
    """Message passed between agents and orchestrator."""
    role: str  # "user", "system", "agent", "orchestrator"
    content: str
    sender: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base class for all Nexus agents."""

    name: str = "base"
    description: str = "Base agent"
    capabilities: list[AgentCapability] = []
    priority: int = 0  # Higher = preferred when multiple agents match

    def __init__(self) -> None:
        self._active = False

    @abstractmethod
    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        """Process a message and return a result."""
        ...

    async def stream_process(self, message: AgentMessage, context: dict[str, Any]) -> AsyncIterator[str]:
        """Stream processing results. Default implementation wraps process()."""
        result = await self.process(message, context)
        yield result.content

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        """Return 0.0-1.0 confidence that this agent can handle the message.
        Override in subclasses for smarter routing.
        """
        return 0.1

    async def initialize(self) -> None:
        """Called when agent is first loaded. Override for setup."""
        self._active = True

    async def shutdown(self) -> None:
        """Called when agent is unloaded. Override for cleanup."""
        self._active = False

    def describe_for_llm(self) -> str:
        """Return a description suitable for LLM-based routing."""
        caps = ", ".join(c.value for c in self.capabilities)
        return f"{self.name}: {self.description} [capabilities: {caps}]"
