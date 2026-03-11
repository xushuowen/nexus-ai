"""Nexus AI - Multi-Agent Assistant System entry point."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path


def _ensure_single_instance() -> None:
    """Ensure only one Nexus instance runs via PID file + psutil double-check."""
    import tempfile
    pid_file = Path(tempfile.gettempdir()) / "nexus_ai.pid"
    current_pid = os.getpid()

    # Step 1: PID file check (fast path)
    if pid_file.exists():
        try:
            old_pid = int(pid_file.read_text().strip())
            if old_pid != current_pid:
                try:
                    import psutil
                    if psutil.pid_exists(old_pid):
                        proc = psutil.Process(old_pid)
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except psutil.TimeoutExpired:
                            proc.kill()
                        print(f"[Nexus] Stopped previous instance: PID {old_pid}")
                except ImportError:
                    pass
        except (ValueError, OSError):
            pass

    # Step 2: psutil scan as backup (catches pythonw without PID file)
    try:
        import psutil
        killed = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.pid == current_pid:
                    continue
                name = (proc.info['name'] or '').lower()
                if 'python' not in name:
                    continue
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'nexus' in cmdline and 'main' in cmdline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed.append(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if killed:
            print(f"[Nexus] Stopped previous instance(s): PID {killed}")
    except ImportError:
        pass

    # Step 3: Write current PID
    try:
        pid_file.write_text(str(current_pid))
    except OSError:
        pass


try:
    _ensure_single_instance()
except ImportError:
    pass  # psutil not available, skip

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
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
from nexus.gateway.hub import MessageHub
from nexus.gateway.api_channel import init_api_channel, set_memory as _set_api_memory
from nexus.gateway.voice_channel import router as _voice_router
from nexus.security.auth import verify_request, verify_websocket, require_auth, get_api_key, get_user_token
from nexus.security.rate_limiter import RateLimiter
from nexus.security import token_vault as _tv
from nexus.skills.skill_loader import SkillLoader
from nexus.core.schedule_runner import ScheduleRunner

import datetime
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
llm_provider: LLMProvider | None = None
active_websockets: list[WebSocket] = []
rate_limiter: RateLimiter | None = None
_schedule_runner: ScheduleRunner | None = None
# Use asyncio.Event instead of a plain bool so waiters can block on it
# (created in lifespan so the event loop is already running).
_init_event: asyncio.Event | None = None

# ── API Channel (MessageHub + REST router, wired in lifespan) ──
_hub = MessageHub()
_api_v1_router = init_api_channel(_hub)


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
            # Atomic write: write to .tmp then rename so a crash mid-write
            # never leaves a corrupt state file that blocks tomorrow's report.
            tmp_path = report_file.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps({"last_date": today}, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp_path.replace(report_file)
            logger.info("Morning report sent and recorded.")


async def _deferred_init(llm, mem, orch, tg, bdg):
    """Initialize heavy components in background so the app starts fast."""
    global _init_event
    try:
        # This is the slow part (ChromaDB downloads ONNX model ~79MB on first run)
        logger.info("Background init: starting memory system...")
        await mem.initialize()
        logger.info("Background init: memory ready")

        # Prune sessions older than 30 days on every startup to keep the DB lean
        try:
            deleted = await mem.session.prune_old_messages(keep_days=30)
            if deleted:
                logger.info(f"Session pruner: removed {deleted} old messages on startup")
        except Exception as e:
            logger.warning(f"Session prune failed: {e}")

        orch.set_memory(mem)

        # Inject memory into api_channel and memory_manager skill
        _set_api_memory(mem)
        if skill_loader:
            mm_skill = next(
                (s for s in skill_loader.list_skills() if s.name == "memory_manager"), None
            )
            if mm_skill and hasattr(mm_skill, "set_memory"):
                mm_skill.set_memory(mem)
                logger.info("Injected memory into memory_manager skill")

        # ── PyramidMemory (optional, controlled by config) ──
        pyramid_cfg = config.load_config().get("pyramid_memory", {})
        if pyramid_cfg.get("enabled", False):
            try:
                await mem.init_pyramid(mem.session, llm)
                logger.info("PyramidMemory started")
            except Exception as e:
                logger.warning(f"PyramidMemory init failed (non-fatal): {e}")

        # Start Telegram bot
        tg.set_orchestrator(orch)
        tg.set_memory(mem)
        tg.set_budget(bdg)
        try:
            await tg.start()
        except Exception as e:
            logger.warning(f"Telegram start failed: {e}")

        # Budget warning: send Telegram push when usage crosses warning_threshold
        async def _budget_warning(ratio: float) -> None:
            pct = int(ratio * 100)
            msg = (
                f"⚠️ **預算警告**\n\n"
                f"今日 Token 使用量已達 **{pct}%**，"
                f"接近每日上限 ({bdg.daily_limit:,} tokens)。\n"
                f"剩餘：{bdg.tokens_remaining:,} tokens"
            )
            try:
                await tg.send_to_owner(msg)
            except Exception as e:
                logger.warning(f"Budget warning notification failed: {e}")

        bdg.set_warning_callback(_budget_warning)

        if _init_event is not None:
            _init_event.set()
        logger.info("Background init: all systems operational!")

        # Pre-warm EasyOCR model in background (avoid cold-start delay on first image)
        try:
            from nexus.agents.vision_agent import warmup_ocr
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, warmup_ocr)
        except Exception as e:
            logger.warning(f"EasyOCR warmup skipped: {e}")

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

        # 主動任務掃描（背景循環，每小時檢查未完成事項）
        try:
            from nexus.core.notifications import proactive_check_loop
            asyncio.create_task(proactive_check_loop(mem, llm, tg))
            logger.info("Proactive task scanner started.")
        except Exception as e:
            logger.warning(f"Proactive scanner start failed (non-fatal): {e}")

    except Exception as e:
        logger.error(f"Background init failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global budget, orchestrator, registry, memory, telegram, rate_limiter, skill_loader, llm_provider, _init_event
    _init_event = asyncio.Event()  # created here so event loop is already running

    logger.info("=" * 50)
    logger.info("  Starting Nexus AI...")
    logger.info("=" * 50)
    config.data_dir()  # ensure data dir exists

    # Initialize lightweight components immediately
    rate_limiter = RateLimiter()
    # Pass rate_limiter into api_channel (router already registered at module load)
    from nexus.gateway import api_channel as _api_ch
    _api_ch._rate_limiter = rate_limiter
    budget = BudgetController()
    router = ModelRouter()
    llm = LLMProvider(budget, router)
    llm_provider = llm
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

    # Wire MessageHub to orchestrator (api_channel router already registered at module load)
    _hub.set_orchestrator(orchestrator)

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
            except Exception as _e:
                logger.debug(f"WebSocket broadcast failed, removing: {_e}")
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
    if llm_provider:
        await llm_provider.close_browser()
    if memory:
        await memory.close()


app = FastAPI(title="Nexus AI", version="0.1.0", lifespan=lifespan)

# Mount REST API channel (hub wired to orchestrator in lifespan)
app.include_router(_api_v1_router)
# Mount Voice channel (Gemini Live API WebSocket)
app.include_router(_voice_router)

# Mount static files
web_dir = Path(__file__).parent / "web"
app.mount("/static", StaticFiles(directory=str(web_dir / "static")), name="static")
templates = Jinja2Templates(directory=str(web_dir / "templates"))


@app.get("/sw.js")
async def service_worker():
    """Serve Service Worker from root scope (required for full PWA coverage)."""
    sw_path = web_dir / "static" / "sw.js"
    return Response(
        content=sw_path.read_bytes(),
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/"},
    )


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

            if _init_event is None or not _init_event.is_set():
                await ws.send_text(json.dumps({
                    "type": "final_answer",
                    "stream": "orchestrator",
                    "content": "System is still initializing, please wait a moment...",
                    "metadata": {},
                }))
                continue

            # Build extra_context for image if provided
            image_path = msg.get("image_path", "")
            extra_ctx = None
            force_agent = None
            if image_path and Path(image_path).exists():
                extra_ctx = {"has_image": True, "image_path": image_path}
                force_agent = "vision"

            # Process through orchestrator
            try:
                async for event in orchestrator.process(user_input, session_id, extra_context=extra_ctx, force_agent=force_agent):
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
                    "stream": "analysis",
                    "content": "⚠️ 處理時發生錯誤，請稍後再試。",
                    "metadata": {},
                }))

    except WebSocketDisconnect:
        if ws in active_websockets:
            active_websockets.remove(ws)
        logger.info(f"WebSocket disconnected. Total: {len(active_websockets)}")


@app.get("/api/status")
async def api_status():
    brain = llm_provider.active_brain if llm_provider else "unknown"
    brain_mode = llm_provider.router.brain_mode if llm_provider else "auto"
    pyramid_cfg = config.load_config().get("pyramid_memory", {})
    pyramid_enabled = pyramid_cfg.get("enabled", False)
    return {
        "status": "running",
        "init_complete": (_init_event is not None and _init_event.is_set()),
        "budget": budget.get_status() if budget else {},
        "agents": [a.name for a in registry.list_agents()] if registry else [],
        "skills": [s.name for s in skill_loader.list_skills()] if skill_loader else [],
        "telegram": telegram._running if telegram else False,
        "brain": brain,
        "brain_mode": brain_mode,
        "pyramid_enabled": pyramid_enabled,
        "auth0_configured": _tv.is_configured(),
    }


# ── Auth0 / Token Vault routes ─────────────────────────────────────────────

@app.get("/auth/login")
async def auth_login():
    """Redirect user to Auth0 Universal Login."""
    from fastapi.responses import RedirectResponse
    if not _tv.is_configured():
        return JSONResponse(status_code=503, content={"error": "Auth0 not configured. Set AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET in .env"})
    return RedirectResponse(_tv.get_login_url())


@app.get("/auth/callback")
async def auth_callback(code: str = "", error: str = ""):
    """Handle Auth0 OAuth callback. Exchanges code for tokens."""
    from fastapi.responses import HTMLResponse as _HTML
    if error:
        return _HTML(f"<h3>Auth error: {error}</h3><a href='/dashboard'>Back</a>")
    if not code:
        return _HTML("<h3>Missing code</h3><a href='/dashboard'>Back</a>")

    tokens = await _tv.exchange_code_for_tokens(code)
    if not tokens:
        return _HTML("<h3>Token exchange failed</h3><a href='/dashboard'>Back</a>")

    access_token = tokens.get("access_token", "")
    # Show a page that stores the token in localStorage and redirects to dashboard
    return _HTML(f"""<!DOCTYPE html>
<html><head><title>Nexus — Auth Complete</title></head>
<body style="background:#0a0a0f;color:#00d4ff;font-family:monospace;text-align:center;padding:80px">
<h2>✅ Authentication Complete</h2>
<p>Nexus agents can now access your connected services via Token Vault.</p>
<script>
  localStorage.setItem('nexus_auth_token', '{access_token}');
  setTimeout(() => window.location.href = '/dashboard', 1500);
</script>
<p>Redirecting to dashboard...</p>
</body></html>""")


@app.get("/auth/logout")
async def auth_logout():
    """Clear local token and redirect to Auth0 logout."""
    from fastapi.responses import HTMLResponse as _HTML
    return _HTML("""<!DOCTYPE html>
<html><head><title>Nexus — Logged Out</title></head>
<body style="background:#0a0a0f;color:#00d4ff;font-family:monospace;text-align:center;padding:80px">
<h2>Logged out</h2>
<script>localStorage.removeItem('nexus_auth_token');</script>
<p><a href="/dashboard" style="color:#00d4ff">Back to Dashboard</a></p>
</body></html>""")


@app.get("/api/auth/connections")
async def api_auth_connections(request: Request):
    """Return Token Vault connection status for the current user.

    Requires Authorization: Bearer <auth0_access_token> header.
    Used by dashboard to show which services the user has connected.
    """
    if not _tv.is_configured():
        return {"auth0_configured": False, "connections": []}

    user_token = get_user_token(request)
    if not user_token:
        return {"auth0_configured": True, "connections": [], "error": "Not authenticated"}

    connections = await _tv.get_user_connections(user_token)
    return {"auth0_configured": True, "connections": connections}


@app.post("/api/brain")
async def api_set_brain(request: Request):
    """切換大腦模式：gemini / gemini_web / local / auto"""
    data = await request.json()
    mode = data.get("mode", "auto")
    if mode not in ("gemini", "gemini_web", "local", "auto"):
        return JSONResponse(status_code=400, content={"error": "無效的模式"})
    if llm_provider:
        llm_provider.router.brain_mode = mode
    return {"ok": True, "brain_mode": mode, "brain": llm_provider.active_brain if llm_provider else "unknown"}


@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    """Accept an image upload.

    Storage strategy:
    - GCS_BUCKET_NAME set → upload to Google Cloud Storage (satisfies GCP requirement)
      + keep a local /tmp copy for VisionAgent OCR processing
    - GCS_BUCKET_NAME not set → local storage (dev mode)
    """
    import uuid
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        return JSONResponse(status_code=400, content={"error": "不支援的檔案格式"})

    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    file_id = uuid.uuid4().hex
    data = await file.read()

    gcs_bucket = os.environ.get("GCS_BUCKET_NAME", "")
    if gcs_bucket:
        # ── Google Cloud Storage path ──
        try:
            from google.cloud import storage as gcs
            blob_name = f"uploads/{file_id}{suffix}"
            loop = asyncio.get_event_loop()

            def _upload():
                client = gcs.Client()
                bucket = client.bucket(gcs_bucket)
                blob = bucket.blob(blob_name)
                blob.upload_from_string(data, content_type=file.content_type)

            await loop.run_in_executor(None, _upload)
            logger.info(f"Uploaded to GCS: gs://{gcs_bucket}/{blob_name}")
        except Exception as e:
            logger.error(f"GCS upload failed: {e}")
            return JSONResponse(status_code=500, content={"error": f"GCS 上傳失敗：{e}"})

        # Keep a local /tmp copy for VisionAgent (OCR needs a file path)
        tmp_dir = Path("/tmp/nexus_uploads")
        tmp_dir.mkdir(exist_ok=True, parents=True)
        local_path = tmp_dir / f"{file_id}{suffix}"
        local_path.write_bytes(data)
        return {"path": str(local_path), "gcs": f"gs://{gcs_bucket}/{blob_name}"}

    else:
        # ── Local storage (dev mode) ──
        if os.environ.get("K_SERVICE"):
            upload_dir = Path("/tmp/nexus_uploads")
        else:
            upload_dir = config.data_dir() / "uploads"
        upload_dir.mkdir(exist_ok=True, parents=True)
        dest = upload_dir / f"{file_id}{suffix}"
        dest.write_bytes(data)
        return {"path": str(dest)}


@app.post("/api/chat")
async def api_chat(request: Request):
    require_auth(request)

    if rate_limiter:
        # Use client IP for per-user rate limiting (falls back to "api" if no IP)
        client_ip = request.client.host if request.client else "api"
        allowed, remaining = rate_limiter.check(client_ip)
        if not allowed:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. Try again in 60 seconds."},
                headers={
                    "X-RateLimit-Limit": str(rate_limiter.max_per_minute),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": "60",
                },
            )

    if _init_event is None or not _init_event.is_set():
        return {"answer": "System is still initializing...", "events": [], "budget": {}}

    body = await request.json()
    user_input = body.get("content", "")
    session_id = body.get("session_id", "default")
    user_token = get_user_token(request)  # Auth0 JWT (None if not logged in)

    events = []
    final_answer = ""
    extra_ctx = {"user_token": user_token} if user_token else None
    async for event in orchestrator.process(user_input, session_id, extra_context=extra_ctx):
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


@app.get("/voice", response_class=HTMLResponse)
async def voice_page(request: Request):
    return templates.TemplateResponse("voice.html", {"request": request})


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
        "status": "operational" if (_init_event is not None and _init_event.is_set()) else "initializing",
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
        "brain": llm_provider.active_brain if llm_provider else "unknown",
        "brain_mode": llm_provider.router.brain_mode if llm_provider else "auto",
    }


if __name__ == "__main__":
    import uvicorn
    host = config.get("app.host", "0.0.0.0")
    port = int(os.getenv("PORT", config.get("app.port", 8000)))
    uvicorn.run("nexus.main:app", host=host, port=port, reload=False)
