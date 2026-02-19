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
from nexus.security.auth import verify_request, verify_websocket, require_auth, get_api_key
from nexus.security.rate_limiter import RateLimiter
from nexus.skills.skill_loader import SkillLoader
from nexus.core.schedule_runner import ScheduleRunner

import datetime
import json
from dataclasses import asdict as _dc_asdict

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
skill_loader: SkillLoader | None = None
active_websockets: list[WebSocket] = []
rate_limiter: RateLimiter | None = None
_schedule_runner: ScheduleRunner | None = None
_init_complete = False


async def _morning_report_check(orch, tg) -> None:
    """啟動時晨報補送：若今天尚未發送且現在是早上 6-11 點，自動送出。"""
    now = datetime.datetime.now()
    if not (6 <= now.hour < 11):
        return

    report_file = config.data_dir() / "morning_report.json"
    today = now.strftime("%Y-%m-%d")

    if report_file.exists():
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            if data.get("last_date") == today:
                logger.info("Morning report already sent today, skipping.")
                return
        except Exception:
            pass

    logger.info("Morning report: generating...")
    weekdays = ["一", "二", "三", "四", "五", "六", "日"]
    weekday = weekdays[now.weekday()]
    prompt = (
        f"現在是 {today} 星期{weekday} 早上 {now.strftime('%H:%M')}。"
        "請給我一份簡短的晨報，包含：今日日期星期、一句激勵話語、今天值得注意的事項提醒。"
        "控制在 150 字以內，語氣輕鬆友善。"
    )

    report_text = ""
    try:
        async for event in orch.process(prompt, session_id="morning_report"):
            if event.event_type == "final_answer":
                report_text = event.content
    except Exception as e:
        logger.error(f"Morning report generation failed: {e}")
        return

    if report_text:
        sent = await tg.send_to_owner(f"🌅 **今日晨報**\n\n{report_text}")
        if sent:
            report_file.write_text(
                json.dumps({"last_date": today}, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.info("Morning report sent and recorded.")


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

        # 啟動循環排程執行器
        global _schedule_runner
        schedule_skill = next(
            (s for s in skill_loader.list_skills() if s.name == "auto_schedule"), None
        )
        if schedule_skill:
            _schedule_runner = ScheduleRunner(schedule_skill, orch, tg)
            _schedule_runner.start()
            logger.info("ScheduleRunner started.")
        else:
            logger.warning("auto_schedule skill not found, ScheduleRunner skipped.")

        # 晨報補送：開機後若是早上且今天尚未發送，自動補送
        await _morning_report_check(orch, tg)

    except Exception as e:
        logger.error(f"Background init failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget, orchestrator, registry, memory, telegram, rate_limiter, skill_loader

    logger.info("=" * 50)
    logger.info("  Starting Nexus AI...")
    logger.info("=" * 50)
    config.data_dir()  # ensure data dir exists

    # Initialize lightweight components immediately
    rate_limiter = RateLimiter()
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

    # Initialize skill system
    skill_loader = SkillLoader()
    await skill_loader.auto_discover()
    orchestrator.set_skill_loader(skill_loader)
    skill_names = [s.name for s in skill_loader.list_skills()]
    logger.info(f"Loaded {len(skill_names)} skills: {skill_names}")

    # Give research agent access to web_search skill
    for agent in registry.list_agents():
        if agent.name == "research" and hasattr(agent, "set_skill_loader"):
            agent.set_skill_loader(skill_loader)
            logger.info("Injected skill_loader into research agent")

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
    if _schedule_runner:
        _schedule_runner.stop()
    if telegram:
        await telegram.stop()
    if skill_loader:
        await skill_loader.shutdown_all()
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
        "api_key": get_api_key() or "",
    })


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if not verify_websocket(ws):
        await ws.close(code=4001, reason="Unauthorized")
        return

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
        "skills": [s.name for s in skill_loader.list_skills()] if skill_loader else [],
        "telegram": telegram._running if telegram else False,
    }


@app.post("/api/chat")
async def api_chat(request: Request):
    require_auth(request)

    if rate_limiter:
        allowed, remaining = rate_limiter.check("api")
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(status_code=429, content={"error": "Rate limit exceeded"})

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


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "app_name": config.get("app.name", "Nexus AI"),
        "api_key": get_api_key() or "",
    })


@app.get("/api/dashboard")
async def api_dashboard():
    """Dashboard data: budget, agents, skills with categories, schedules, channel status."""
    schedules: list = []
    if skill_loader:
        schedule_skill = next(
            (s for s in skill_loader.list_skills() if s.name == "auto_schedule"), None
        )
        if schedule_skill and hasattr(schedule_skill, "get_schedules"):
            try:
                raw = schedule_skill.get_schedules()
                schedules = [_dc_asdict(e) for e in raw]
            except Exception:
                pass

    return {
        "status": "operational" if _init_complete else "initializing",
        "budget": budget.get_status() if budget else {},
        "agents": [
            {"name": a.name, "description": getattr(a, "description", "")}
            for a in registry.list_agents()
        ] if registry else [],
        "skills": [
            {
                "name": s.name,
                "description": getattr(s, "description", ""),
                "category": getattr(s, "category", "general"),
            }
            for s in skill_loader.list_skills()
        ] if skill_loader else [],
        "schedules": schedules,
        "telegram": bool(telegram and getattr(telegram, "_running", False)),
    }


if __name__ == "__main__":
    import uvicorn
    host = config.get("app.host", "0.0.0.0")
    port = int(os.getenv("PORT", config.get("app.port", 8000)))
    uvicorn.run("nexus.main:app", host=host, port=port, reload=False)
