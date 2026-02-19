"""Titan Protocol — 3-part structured output parsing (Memory/Action/Reply).

Inspired by Project Golem's Titan output contract. LLM responses are parsed
into three sections so the orchestrator can automatically store memories,
execute actions, and deliver the user-facing reply.

Backward-compatible: if the LLM does not follow the format, the entire
response is treated as the reply section.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# Section markers — keep them distinctive so the LLM can follow easily.
_MEMORY_TAG = "[NEXUS_MEMORY]"
_ACTION_TAG = "[NEXUS_ACTION]"
_REPLY_TAG = "[NEXUS_REPLY]"

_SECTION_RE = re.compile(
    r"\[NEXUS_(?:MEMORY|ACTION|REPLY)\]",
    re.IGNORECASE,
)


@dataclass
class TitanResult:
    """Parsed three-part LLM response."""

    memory: str = ""          # Facts / context to remember
    actions: list[dict] = field(default_factory=list)  # Structured actions
    reply: str = ""           # User-facing answer


class TitanProtocol:
    """Inject format instructions into prompts and parse structured responses."""

    FORMAT_INSTRUCTIONS = (
        "\n\n--- OUTPUT FORMAT ---\n"
        "When you have information worth remembering or actions to perform, "
        "structure your response using these OPTIONAL sections. "
        "If you have nothing to remember or no action to take, you may omit those sections.\n\n"
        "[NEXUS_MEMORY]\n"
        "(Facts, preferences, or context worth storing for future conversations. "
        "One fact per line. Omit this section if there is nothing new to remember.)\n\n"
        "[NEXUS_ACTION]\n"
        "(JSON array of actions, e.g. [{\"type\": \"search\", \"query\": \"...\"}]. "
        "Omit this section if no action is needed.)\n\n"
        "[NEXUS_REPLY]\n"
        "(Your response to the user. This section is REQUIRED — "
        "everything after this tag is shown to the user.)\n"
        "--- END FORMAT ---\n"
    )

    @staticmethod
    def inject_prompt(system_prompt: str) -> str:
        """Append Titan format instructions to a system prompt."""
        return system_prompt + TitanProtocol.FORMAT_INSTRUCTIONS

    @staticmethod
    def parse(response: str) -> TitanResult:
        """Parse an LLM response into TitanResult.

        If the response does not contain any section tags, the entire text
        is treated as the reply (backward-compatible).
        """
        result = TitanResult()

        # Quick check — if no tags found, treat entire response as reply
        if not _SECTION_RE.search(response):
            result.reply = response.strip()
            return result

        # Split by tags
        memory_text = _extract_section(response, _MEMORY_TAG, _ACTION_TAG)
        action_text = _extract_section(response, _ACTION_TAG, _REPLY_TAG)
        reply_text = _extract_section(response, _REPLY_TAG, None)

        # Memory
        result.memory = memory_text.strip()

        # Actions — try to parse as JSON array
        action_text = action_text.strip()
        if action_text:
            import json
            try:
                parsed = json.loads(action_text)
                if isinstance(parsed, list):
                    result.actions = parsed
                elif isinstance(parsed, dict):
                    result.actions = [parsed]
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON — store as raw text action
                if action_text:
                    result.actions = [{"type": "raw", "content": action_text}]

        # Reply — required, fallback to full response
        result.reply = reply_text.strip()
        if not result.reply:
            # Fallback: everything that isn't in MEMORY or ACTION
            result.reply = response.strip()

        return result


def _extract_section(text: str, start_tag: str, end_tag: str | None) -> str:
    """Extract text between start_tag and end_tag (or end of string)."""
    start_idx = text.upper().find(start_tag.upper())
    if start_idx == -1:
        return ""

    content_start = start_idx + len(start_tag)

    if end_tag is not None:
        end_idx = text.upper().find(end_tag.upper(), content_start)
        if end_idx == -1:
            return text[content_start:]
        return text[content_start:end_idx]
    else:
        return text[content_start:]
