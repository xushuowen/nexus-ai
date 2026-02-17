"""Base tool class - register, execute, and self-describe for LLM function calling."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParameter:
    """Describes a tool parameter for LLM function calling."""
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: list[str] | None = None


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: str
    data: Any = None
    error: str | None = None


class BaseTool(ABC):
    """Abstract base class for all Nexus tools.
    Each tool is an independent module that can be auto-discovered and
    described to the LLM for function calling."""

    name: str = "base_tool"
    description: str = "Base tool"
    category: str = "general"
    parameters: list[ToolParameter] = []
    requires_confirmation: bool = False

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters."""
        ...

    def describe_for_llm(self) -> dict[str, Any]:
        """Return OpenAI-compatible function description for LLM."""
        properties = {}
        required = []
        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            properties[param.name] = prop
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def short_description(self) -> str:
        """One-line description for listing."""
        return f"{self.name}: {self.description}"

    async def validate(self, **kwargs) -> str | None:
        """Validate parameters before execution. Returns error message or None."""
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                return f"Missing required parameter: {param.name}"
        return None

    async def initialize(self) -> None:
        """Called when tool is first loaded."""
        pass

    async def shutdown(self) -> None:
        """Called when tool is unloaded."""
        pass
