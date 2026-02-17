"""Nexus AI - Multi-Agent Assistant System entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from nexus import config
from nexus.core.budget import BudgetController
from nexus.core.orchestrator import Orchestrator
from nexus.core.agent_registry import AgentRegistry
from nexus.core.three_stream import StreamEvent
from nexus.providers.llm_provider import LLMProvider
from nexus.providers.model_config import ModelRouter
from nexus.memory.hybrid_store import HybridMemory
from nexus.gateway.telegram_channel import TelegramChannel

load_dotenv()

logging.basicConfig(
    level=getattr(logging, config.get("logging.level", "INFO")),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("nexus")

# ── Global components (initialized in lifespan) ──
budget: BudgetController | None = None
orchestrator: Orchestrator | None = None
registry: AgentRegistry | None = None
memory: HybridMemory | None = None
telegram: TelegramChannel | None = None
active_websockets: list[WebSocket] = []
_init_complete = False


async def _deferred_init(llm, mem, orch, tg, bdg):
    """Initialize heavy components in background so the app starts fast."""
    global _init_complete
    try:
        # This is the slow part (ChromaDB downloads ONNX model ~79MB on first run)
        logger.info("Background init: starting memory system...")
        await mem.initialize()
        logger.info("Background init: memory ready")

        orch.set_memory(mem)

        # Start Telegram bot
        tg.set_orchestrator(orch)
        tg.set_memory(mem)
        tg.set_budget(bdg)
        try:
            await tg.start()
        except Exception as e:
            logger.warning(f"Telegram start failed: {e}")

        _init_complete = True
        logger.info("Background init: all systems operational!")
    except Exception as e:
        logger.error(f"Background init failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget, orchestrator, registry, memory, telegram

    logger.info("=" * 50)
    logger.info("  Starting Nexus AI...")
    logger.info("=" * 50)
    config.data_dir()  # ensure data dir exists

    # Initialize lightweight components immediately
    budget = BudgetController()
    router = ModelRouter()
    llm = LLMProvider(budget, router)
    registry = AgentRegistry()
    memory = HybridMemory()

    # Auto-discover agents and inject dependencies
    await registry.auto_discover()
    for agent in registry.list_agents():
        if hasattr(agent, "set_llm"):
            agent.set_llm(llm)
        if hasattr(agent, "set_dependencies"):
            if agent.name == "knowledge":
                agent.set_dependencies(memory, llm)
            elif agent.name == "optimizer":
                agent.set_dependencies(budget, memory)
    logger.info(f"Loaded {len(registry.list_agents())} agents: {[a.name for a in registry.list_agents()]}")

    orchestrator = Orchestrator(budget, llm, router, registry)

    # Broadcast events to all connected WebSockets
    async def broadcast_event(event: StreamEvent):
        msg = json.dumps({
            "type": event.event_type,
            "stream": event.stream,
            "content": event.content,
            "metadata": event.metadata,
        })
        disconnected = []
        for ws in active_websockets:
            try:
                await ws.send_text(msg)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            active_websockets.remove(ws)

    orchestrator.on_event(broadcast_event)

    telegram = TelegramChannel()

    port = int(os.getenv("PORT", config.get("app.port", 8000)))
    logger.info("=" * 50)
    logger.info("  Nexus AI accepting requests!")
    logger.info(f"  Web UI: http://localhost:{port}")
    logger.info("  Heavy init running in background...")
    logger.info("=" * 50)

    # Start heavy initialization in background (ChromaDB, Telegram, etc.)
    asyncio.create_task(_deferred_init(llm, memory, orchestrator, telegram, budget))

    yield

    # Shutdown
    logger.info("Shutting down Nexus AI...")
    if telegram:
        await telegram.stop()
    await registry.shutdown_all()
    if memory:
        await memory.close()


app = FastAPI(title="Nexus AI", version="0.1.0", lifespan=lifespan)

# Mount static files
web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(web_dir / "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "app_name": config.get("app.name", "Nexus AI"),
    })


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_websockets.append(ws)
    logger.info(f"WebSocket connected. Total: {len(active_websockets)}")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            user_input = msg.get("content", "")
            session_id = msg.get("session_id", "default")

            if not user_input.strip():
                continue

            if not _init_complete:
                await ws.send_text(json.dumps({
                    "type": "final_answer",
                    "stream": "orchestrator",
                    "content": "System is still initializing, please wait a moment...",
                    "metadata": {},
                }))
                continue

            # Process through orchestrator
            try:
                async for event in orchestrator.process(user_input, session_id):
                    await ws.send_text(json.dumps({
                        "type": event.event_type,
                        "stream": event.stream,
                        "content": event.content,
                        "metadata": event.metadata,
                    }))
            except Exception as e:
                logger.error(f"Processing error: {e}")
                await ws.send_text(json.dumps({
                    "type": "error",
                    "content": str(e),
                }))

    except WebSocketDisconnect:
        if ws in active_websockets:
            active_websockets.remove(ws)
        logger.info(f"WebSocket disconnected. Total: {len(active_websockets)}")


@app.get("/api/status")
async def api_status():
    return {
        "status": "running",
        "init_complete": _init_complete,
        "budget": budget.get_status() if budget else {},
        "agents": [a.name for a in registry.list_agents()] if registry else [],
        "telegram": telegram._running if telegram else False,
    }


@app.post("/api/chat")
async def api_chat(request: Request):
    if not _init_complete:
        return {"answer": "System is still initializing...", "events": [], "budget": {}}

    body = await request.json()
    user_input = body.get("content", "")
    session_id = body.get("session_id", "default")

    events = []
    final_answer = ""
    async for event in orchestrator.process(user_input, session_id):
        events.append({
            "type": event.event_type,
            "content": event.content,
        })
        if event.event_type == "final_answer":
            final_answer = event.content

    return {
        "answer": final_answer,
        "events": events,
        "budget": budget.get_status(),
    }


if __name__ == "__main__":
    import uvicorn
    host = config.get("app.host", "0.0.0.0")
    port = int(os.getenv("PORT", config.get("app.port", 8000)))
    uvicorn.run("nexus.main:app", host=host, port=port, reload=False)
