"""Self-verification using the same LLM with different prompts."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

VERIFY_PROMPT_TEMPLATE = """You are a critical verification assistant. Your job is to check whether the following answer is correct, complete, and logically sound.

Original Question: {question}

Proposed Answer: {answer}

Please analyze:
1. Is the answer factually correct?
2. Is it logically consistent?
3. Does it fully address the question?
4. Any errors or omissions?

Rate your confidence (0.0-1.0) that the answer is correct.
Respond in JSON: {{"confidence": 0.X, "issues": ["..."], "suggestion": "..."}}"""


@dataclass
class VerificationResult:
    confidence: float
    issues: list[str]
    suggestion: str
    passed: bool


class Verifier:
    """Self-check using the same model with a verification prompt."""

    def __init__(self, confidence_threshold: float = 0.7) -> None:
        self.confidence_threshold = confidence_threshold

    async def verify(
        self,
        question: str,
        answer: str,
        llm_call,  # async callable(prompt) -> str
    ) -> VerificationResult:
        """Verify an answer using the LLM as a self-checker."""
        import json

        prompt = VERIFY_PROMPT_TEMPLATE.format(question=question, answer=answer)
        try:
            response = await llm_call(prompt)
            # Try to parse JSON from response
            # Handle case where LLM wraps in markdown
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            data = json.loads(text)
            confidence = float(data.get("confidence", 0.5))
            issues = data.get("issues", [])
            suggestion = data.get("suggestion", "")
            return VerificationResult(
                confidence=confidence,
                issues=issues,
                suggestion=suggestion,
                passed=confidence >= self.confidence_threshold,
            )
        except Exception as e:
            logger.warning(f"Verification parse error: {e}")
            return VerificationResult(
                confidence=0.5,
                issues=[f"Verification failed to parse: {e}"],
                suggestion="",
                passed=True,  # Don't block on verification failures
            )

    async def quick_check(
        self,
        answer: str,
        llm_call,
    ) -> float:
        """Quick confidence check without full verification. Returns 0.0-1.0."""
        prompt = (
            f"Rate the quality and correctness of this response on a scale of 0.0 to 1.0. "
            f"Respond with just a number.\n\nResponse: {answer[:500]}"
        )
        try:
            resp = await llm_call(prompt)
            return float(resp.strip())
        except (ValueError, Exception):
            return 0.5
