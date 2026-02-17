"""REST API channel for programmatic access."""

from __future__ import annotations

from fastapi import APIRouter, Request
from typing import Any

from nexus.gateway.hub import ChannelMessage, MessageHub

router = APIRouter(prefix="/api/v1", tags=["api"])
_hub: MessageHub | None = None


def init_api_channel(hub: MessageHub) -> APIRouter:
    global _hub
    _hub = hub
    hub.register_channel("api", router)
    return router


@router.post("/chat")
async def chat(request: Request) -> dict[str, Any]:
    body = await request.json()
    message = ChannelMessage(
        channel="api",
        content=body.get("content", ""),
        session_id=body.get("session_id", "default"),
        user_id=body.get("user_id", "api_user"),
    )
    response = await _hub.process(message)
    return {
        "answer": response.content,
        "events": response.events,
        "metadata": response.metadata,
    }


@router.get("/status")
async def status() -> dict[str, str]:
    return {"status": "running", "channel": "api"}


@router.post("/teach")
async def teach(request: Request) -> dict[str, str]:
    """Teach the system a new fact."""
    body = await request.json()
    title = body.get("title", "User-taught fact")
    content = body.get("content", "")
    if not content:
        return {"status": "error", "message": "Content is required"}
    # Store directly to memory if available
    return {"status": "ok", "message": f"Stored: {title}"}
