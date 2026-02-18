"""System info skill - display system and Nexus status."""

from __future__ import annotations

import os
import platform
import sys
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class SysInfoSkill(BaseSkill):
    name = "sysinfo"
    description = "系統資訊 — 顯示作業系統、硬體和 Nexus 狀態"
    triggers = ["系統", "system", "sysinfo", "硬體", "hardware", "系統資訊"]
    category = "utility"
    requires_llm = False

    instructions = "顯示系統硬體資訊和 Nexus AI 運行狀態。"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        lines = ["🖥️ **系統資訊**\n"]

        # OS info
        lines.append(f"**作業系統**: {platform.system()} {platform.release()}")
        lines.append(f"**版本**: {platform.version()}")
        lines.append(f"**架構**: {platform.machine()}")
        lines.append(f"**處理器**: {platform.processor() or 'N/A'}")
        lines.append(f"**Python**: {sys.version.split()[0]}")
        lines.append(f"**主機名稱**: {platform.node()}")

        # Disk usage
        try:
            import shutil
            usage = shutil.disk_usage("/") if platform.system() != "Windows" else shutil.disk_usage("C:\\")
            total_gb = usage.total / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            used_pct = (usage.used / usage.total) * 100
            lines.append(f"\n💾 **磁碟**: {total_gb:.1f} GB（已用 {used_pct:.0f}%，剩餘 {free_gb:.1f} GB）")
        except Exception:
            pass

        # Memory (try psutil, fallback gracefully)
        try:
            import psutil
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024 ** 3)
            avail_gb = mem.available / (1024 ** 3)
            lines.append(f"🧠 **記憶體**: {total_gb:.1f} GB（可用 {avail_gb:.1f} GB，使用率 {mem.percent}%）")
            lines.append(f"⚡ **CPU 使用率**: {psutil.cpu_percent(interval=0.5)}%")
            lines.append(f"🔢 **CPU 核心**: {psutil.cpu_count(logical=True)}")
        except ImportError:
            lines.append("\n💡 安裝 `psutil` 可顯示更多硬體資訊")

        # Environment
        lines.append(f"\n🌐 **環境變數**:")
        lines.append(f"  GROQ_API_KEY: {'✅ 已設定' if os.getenv('GROQ_API_KEY') else '❌ 未設定'}")
        lines.append(f"  GEMINI_API_KEY: {'✅ 已設定' if os.getenv('GEMINI_API_KEY') else '❌ 未設定'}")
        lines.append(f"  TELEGRAM_BOT_TOKEN: {'✅ 已設定' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌ 未設定'}")
        lines.append(f"  NEXUS_API_KEY: {'✅ 已設定' if os.getenv('NEXUS_API_KEY') else '⚠️ 未設定（本地模式）'}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)
