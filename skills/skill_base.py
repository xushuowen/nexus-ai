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
    synonyms: dict[str, list[str]] = {}  # Extra aliases: {"trigger": ["alias1", "alias2"]}
    category: str = "general"
    requires_llm: bool = False        # Whether this skill needs LLM to run

    # ── Level 2: Content (loaded on trigger) ──
    instructions: str = ""            # Detailed instructions for the skill
    output_format: str = ""           # Expected output format

    @staticmethod
    def _trigger_matches(trigger: str, text_lower: str) -> bool:
        """Match trigger against lowercased text.

        ASCII triggers: word-boundary matching to avoid false positives
        (e.g. 'note' inside 'annotate').
        CJK/mixed triggers: substring search; short CJK triggers (≤2 chars)
        also require a non-CJK boundary or start/end to reduce noise.
        """
        if re.match(r'^[a-z0-9 _-]+$', trigger):
            return bool(re.search(r'\b' + re.escape(trigger) + r'\b', text_lower))
        # Short CJK triggers (≤2 chars) — guard against embedded false matches
        if len(trigger) <= 2 and re.match(r'^[\u4e00-\u9fff]+$', trigger):
            # Prefer boundary match (preceded/followed by non-CJK or start/end)
            pat = r'(?:^|(?<=\W))' + re.escape(trigger) + r'(?=\W|$)'
            return bool(re.search(pat, text_lower)) or trigger in text_lower
        return trigger in text_lower

    def match_score(self, text: str) -> float:
        """Level 1: Check how well input matches this skill's triggers or intent patterns.

        Scoring:
        - Each matching trigger keyword: 1 + len*0.08 (longer = more specific = higher)
        - Each matching synonym: 0.8 points
        - Each matching intent pattern: 1.2 points (regex = more precise)
        Returns a float but callers may cast to int; higher = better match.
        """
        text_lower = text.lower()
        score = 0.0
        for t in self.triggers:
            if self._trigger_matches(t.lower(), text_lower):
                score += 1.0 + len(t) * 0.08
            # Also check synonyms for this trigger
            for alias in self.synonyms.get(t, []):
                if self._trigger_matches(alias.lower(), text_lower):
                    score += 0.8
                    break  # count only once per trigger
        for pattern in self.intent_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score += 1.2
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
