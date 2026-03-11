"""Windows desktop notification + proactive task scanning.

Sends native Windows toast notifications for:
- Upcoming calendar events
- Uncompleted tasks detected in memory
- Proactive AI nudges
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Windows Toast (via PowerShell, no extra deps) ──

def send_toast(title: str, message: str, duration: int = 8) -> None:
    """Send a Windows balloon/toast notification via PowerShell.

    Non-blocking: launches PowerShell as a detached background process.
    """
    # Escape double-quotes for PS string
    t = title.replace('"', "'")
    m = message.replace('"', "'").replace('\n', ' ')

    ps_script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        "$n.Visible = $true; "
        f'$n.ShowBalloonTip({duration * 1000}, "{t}", "{m}", '
        "[System.Windows.Forms.ToolTipIcon]::Info); "
        f"Start-Sleep -Milliseconds {duration * 1000 + 500}; "
        "$n.Dispose()"
    )
    try:
        kwargs = {}
        if hasattr(subprocess, "CREATE_NO_WINDOW"):  # Windows only
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", ps_script],
            **kwargs,
        )
    except Exception as e:
        logger.warning("Toast notification failed: %s", e)


# ── Proactive Task Scanner ──

_UNFINISHED_PATTERNS = [
    "我要", "我想", "幫我", "記得", "提醒我", "之後", "待辦",
    "todo", "remember to", "remind me", "i need to", "i want to",
]

_SCAN_INTERVAL = 3600   # scan every 1 hour
_LAST_SCAN: float = 0.0


async def scan_uncompleted_tasks(memory, llm) -> list[str]:
    """Scan recent memory for uncompleted tasks/intentions.

    Returns list of task strings found.
    """
    if not memory or not llm:
        return []

    try:
        # Search for intention-like memories
        results = []
        for pattern in ["待辦", "我要", "提醒", "todo", "未完成"]:
            hits = await memory.search(pattern, top_k=3)
            results.extend(hits)

        if not results:
            return []

        # Deduplicate by content
        seen = set()
        unique = []
        for r in results:
            c = r.get("content", "")[:100]
            if c and c not in seen:
                seen.add(c)
                unique.append(c)

        if not unique:
            return []

        # Let LLM filter actual uncompleted tasks
        snippet = "\n".join(f"- {c}" for c in unique[:8])
        prompt = (
            f"以下是從記憶中找到的條目：\n{snippet}\n\n"
            "請找出其中「使用者說要做但可能還沒做完」的事項。\n"
            "只列出真正像待辦事項的（不要列一般知識或已完成的）。\n"
            "每行一個，最多3個。若沒有則回傳『無』。"
        )
        response = await llm.complete(prompt, task_type="general", source="task_scanner")
        if "無" in response or not response.strip():
            return []

        tasks = [line.strip().lstrip("•-· ") for line in response.strip().split("\n") if line.strip()]
        return [t for t in tasks if len(t) > 3][:3]

    except Exception as e:
        logger.warning("Task scanner error: %s", e)
        return []


async def proactive_check_loop(memory, llm, telegram=None) -> None:
    """Background loop: periodically scan for uncompleted tasks and nudge user."""
    global _LAST_SCAN
    await asyncio.sleep(300)  # Wait 5 min after startup before first scan

    while True:
        try:
            now = time.time()
            hour = datetime.now().hour

            # Only run during waking hours (8am - 11pm)
            if 8 <= hour <= 23 and now - _LAST_SCAN >= _SCAN_INTERVAL:
                _LAST_SCAN = now
                tasks = await scan_uncompleted_tasks(memory, llm)

                if tasks:
                    task_list = "\n".join(f"• {t}" for t in tasks)
                    msg = f"你有 {len(tasks)} 件事可能還沒完成：\n{task_list}"
                    logger.info("Proactive nudge: %d uncompleted tasks found", len(tasks))

                    # Windows toast
                    send_toast("Nexus AI 提醒", msg)

                    # Telegram push if available
                    if telegram:
                        try:
                            await telegram.send_message(
                                f"🔔 **Nexus 主動提醒**\n\n{msg}\n\n"
                                "有需要我幫忙處理嗎？"
                            )
                        except Exception as e:
                            logger.warning("Telegram proactive push failed: %s", e)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Proactive check loop error: %s", e)

        await asyncio.sleep(600)  # check every 10 min whether conditions are met
