"""Common sense rules for local filtering before LLM calls.
Zero token cost - all rule matching is local."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class CommonSenseRule:
    """A simple rule for filtering or classifying queries."""
    name: str
    pattern: str  # regex pattern
    category: str
    confidence: float = 0.9
    response_hint: str = ""


# Built-in common sense rules
DEFAULT_RULES: list[CommonSenseRule] = [
    # Greetings
    CommonSenseRule("greeting", r"^(hi|hello|hey|yo|good\s+(morning|afternoon|evening))\b",
                    "greeting", 0.95, "Respond with a friendly greeting"),
    # Simple math
    CommonSenseRule("simple_math", r"^\d+\s*[\+\-\*\/]\s*\d+\s*$",
                    "math", 0.99, "Calculate locally"),
    # Time/date questions
    CommonSenseRule("time_query", r"\b(what\s+time|current\s+time|what\s+day)\b",
                    "time", 0.9, "Return system time"),
    # Identity questions
    CommonSenseRule("identity", r"\b(who\s+are\s+you|your\s+name|what\s+are\s+you)\b",
                    "identity", 0.95, "I am Nexus AI"),
    # Thank you
    CommonSenseRule("thanks", r"^(thanks?|thank\s+you|thx)\b",
                    "thanks", 0.95, "You're welcome!"),
    # Goodbye
    CommonSenseRule("goodbye", r"^(bye|goodbye|see\s+you|quit|exit)\b",
                    "goodbye", 0.95, "Goodbye! Feel free to come back anytime."),
    # Code request detection
    CommonSenseRule("code_request", r"\b(write|create|code|implement|function|class|script)\b.*\b(python|javascript|code|program)\b",
                    "coding", 0.7),
    # Web search detection
    CommonSenseRule("search_request", r"\b(search|find|look\s+up|google|latest|news|current)\b",
                    "web_search", 0.7),
    # Explanation request
    CommonSenseRule("explain", r"\b(explain|what\s+is|define|describe|how\s+does)\b",
                    "explanation", 0.6),
    # File operations
    CommonSenseRule("file_ops", r"\b(read|write|create|delete|open|save|file|folder|directory)\b",
                    "file_operation", 0.6),
]


class CommonSenseFilter:
    """Applies common sense rules to classify and filter queries locally."""

    def __init__(self, extra_rules: list[CommonSenseRule] | None = None) -> None:
        self.rules = DEFAULT_RULES + (extra_rules or [])

    def classify(self, query: str) -> list[tuple[CommonSenseRule, float]]:
        """Classify a query against all rules. Returns matched rules with scores."""
        matches = []
        query_lower = query.lower().strip()
        for rule in self.rules:
            match = re.search(rule.pattern, query_lower, re.IGNORECASE)
            if match:
                matches.append((rule, rule.confidence))
        matches.sort(key=lambda x: -x[1])
        return matches

    def get_category(self, query: str) -> str | None:
        """Get the top category for a query."""
        matches = self.classify(query)
        return matches[0][0].category if matches else None

    def can_answer_locally(self, query: str) -> tuple[bool, str]:
        """Check if the query can be answered without LLM.
        Returns (can_answer, response)."""
        matches = self.classify(query)
        if not matches:
            return False, ""

        rule, conf = matches[0]
        if rule.category == "greeting":
            return True, "Hello! I'm Nexus AI. How can I help you today?"
        if rule.category == "thanks":
            return True, "You're welcome! Let me know if you need anything else."
        if rule.category == "goodbye":
            return True, "Goodbye! Feel free to come back anytime."
        if rule.category == "identity":
            return True, "I'm Nexus AI, a multi-agent AI assistant designed to help with various tasks."
        if rule.category == "math":
            try:
                result = eval(query.strip())  # Safe for simple math patterns
                return True, f"The answer is {result}"
            except Exception:
                pass
        if rule.category == "time":
            import datetime
            now = datetime.datetime.now()
            return True, f"Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}"

        return False, ""

    def get_complexity_hint(self, query: str) -> str:
        """Estimate query complexity: 'simple', 'moderate', 'complex'."""
        word_count = len(query.split())
        matches = self.classify(query)

        if not matches:
            return "moderate"

        top_cat = matches[0][0].category
        if top_cat in ("greeting", "thanks", "goodbye", "identity", "time", "math"):
            return "simple"
        if word_count > 50 or len(matches) > 2:
            return "complex"
        return "moderate"
