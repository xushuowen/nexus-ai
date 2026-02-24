"""Three-layer skill base class (inspired by OpenClaw + @7.alex.huang's notes).

Architecture:
  Level 1 (Index):    name + description + triggers → always loaded, LLM decides activation
  Level 2 (Content):  instructions + output_format → loaded only when triggered
  Level 3 (Appendix): execute() logic, templates → loaded only at execution time
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillResult:
    """Result from a skill execution."""
    content: str
    success: bool = True
    source: str = ""
    tokens_used: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSkill(ABC):
    """Abstract base for all Nexus skills.

    Subclasses define three layers:
      L1: name, description, triggers (class attributes)
      L2: instructions, output_format (class attributes)
      L3: execute() method
    """

    # ── Level 1: Index (always loaded) ──
    name: str = "base"
    description: str = "Base skill"
    triggers: list[str] = []          # Keywords that activate this skill
    intent_patterns: list[str] = []   # Regex patterns for intent matching
    category: str = "general"
    requires_llm: bool = False        # Whether this skill needs LLM to run

    # ── Level 2: Content (loaded on trigger) ──
    instructions: str = ""            # Detailed instructions for the skill
    output_format: str = ""           # Expected output format

    def match_score(self, text: str) -> int:
        """Level 1: Check how well input matches this skill's triggers or intent patterns."""
        text_lower = text.lower()
        score = sum(1 for t in self.triggers if t.lower() in text_lower)
        # Intent patterns catch natural language that doesn't use exact trigger words
        if score == 0:
            for pattern in self.intent_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    score += 1
                    break  # One intent match is enough to activate
        return score

    def get_index(self) -> dict[str, str]:
        """Level 1: Return index entry for LLM routing."""
        return {
            "name": self.name,
            "description": self.description,
            "triggers": ", ".join(self.triggers),
        }

    def get_content(self) -> dict[str, str]:
        """Level 2: Return detailed content for execution context."""
        return {
            "instructions": self.instructions,
            "output_format": self.output_format,
        }

    @abstractmethod
    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        """Level 3: Execute the skill."""
        ...

    async def initialize(self) -> None:
        """Called when skill is loaded."""
        pass

    async def shutdown(self) -> None:
        """Called when skill is unloaded."""
        pass
