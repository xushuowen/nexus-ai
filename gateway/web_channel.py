"""Web UI + WebSocket channel for the Matrix-style interface."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse

from nexus.gateway.hub import ChannelMessage, MessageHub

logger = logging.getLogger(__name__)
router = APIRouter(tags=["web"])
_hub: MessageHub | None = None
_active_ws: list[WebSocket] = []


def init_web_channel(hub: MessageHub) -> APIRouter:
    global _hub
    _hub = hub
    hub.register_channel("web", router)
    return router


@router.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    _active_ws.append(ws)
    logger.info(f"Web WebSocket connected. Total: {len(_active_ws)}")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            message = ChannelMessage(
                channel="web",
                content=msg.get("content", ""),
                session_id=msg.get("session_id", "default"),
                user_id="web_user",
            )

            # Stream events back
            if _hub and _hub._orchestrator:
                try:
                    async for event in _hub._orchestrator.process(
                        message.content, message.session_id
                    ):
                        await ws.send_text(json.dumps({
                            "type": event.event_type,
                            "stream": event.stream,
                            "content": event.content,
                            "metadata": event.metadata,
                        }))
                except Exception as e:
                    await ws.send_text(json.dumps({
                        "type": "error",
                        "content": str(e),
                    }))
            else:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "content": "System not initialized",
                }))

    except WebSocketDisconnect:
        if ws in _active_ws:
            _active_ws.remove(ws)
        logger.info(f"Web WebSocket disconnected. Total: {len(_active_ws)}")


async def broadcast(event: dict[str, Any]) -> None:
    """Broadcast an event to all connected web clients."""
    msg = json.dumps(event)
    disconnected = []
    for ws in _active_ws:
        try:
            await ws.send_text(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _active_ws.remove(ws)
