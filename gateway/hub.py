"""Central message hub - routes messages between channels and the orchestrator."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)


@dataclass
class ChannelMessage:
    """A message from any channel (web, telegram, api)."""
    channel: str  # "web", "telegram", "api"
    content: str
    session_id: str = "default"
    user_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HubResponse:
    """Response from the hub to be sent back to the channel."""
    content: str
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class MessageHub:
    """Central hub that receives messages from all channels and dispatches
    them to the orchestrator."""

    def __init__(self) -> None:
        self._orchestrator = None
        self._channels: dict[str, Any] = {}
        self._middleware: list[Callable] = []

    def set_orchestrator(self, orchestrator) -> None:
        self._orchestrator = orchestrator

    def register_channel(self, name: str, channel: Any) -> None:
        self._channels[name] = channel
        logger.info(f"Registered channel: {name}")

    def add_middleware(self, middleware: Callable) -> None:
        self._middleware.append(middleware)

    async def process(self, message: ChannelMessage) -> HubResponse:
        """Process a message from any channel through the orchestrator."""
        # Apply middleware
        for mw in self._middleware:
            try:
                message = await mw(message)
            except Exception as e:
                logger.warning(f"Middleware error: {e}")

        if not self._orchestrator:
            return HubResponse(content="System not initialized.")

        events = []
        final_answer = ""

        try:
            async for event in self._orchestrator.process(
                message.content, message.session_id
            ):
                events.append({
                    "type": event.event_type,
                    "stream": event.stream,
                    "content": event.content,
                })
                if event.event_type == "final_answer":
                    final_answer = event.content
        except Exception as e:
            logger.error(f"Hub processing error: {e}")
            final_answer = f"Error processing your request: {e}"

        return HubResponse(content=final_answer, events=events)
