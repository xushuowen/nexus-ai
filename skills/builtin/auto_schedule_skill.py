"""Auto Schedule Skill — 循環排程管理，讓 Nexus 在特定時間自動執行任務並透過 Telegram 通知。"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, asdict
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


WEEKDAY_MAP = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

_DAYS_LABEL = {
    "daily": "每天", "weekdays": "每個工作日", "weekends": "每個週末",
    "mon": "每週一", "tue": "每週二", "wed": "每週三",
    "thu": "每週四", "fri": "每週五", "sat": "每週六", "sun": "每週日",
}


@dataclass
class ScheduleEntry:
    id: str
    name: str
    action: str
    time: str           # "06:00"
    days: str           # "daily" | "weekdays" | "weekends" | "mon,wed,fri"
    last_run_date: str = ""
    enabled: bool = True


class AutoScheduleSkill(BaseSkill):
    name = "auto_schedule"
    description = "循環排程 — 設定 Nexus 在特定時間自動執行任務並透過 Telegram 通知"
    triggers = [
        "排程", "schedule", "每天", "每週", "每日", "定時",
        "循環提醒", "自動提醒", "固定時間", "設定排程",
    ]
    category = "automation"
    requires_llm = False

    instructions = (
        "循環排程系統：\n"
        "• 新增：「每天早上6點 生成晨報」\n"
        "         「每週一早上8點 提醒我回顧本週計劃」\n"
        "         「每個工作日下午5點 總結今日工作」\n"
        "         「每週一三五早上7點 英文單字練習」\n"
        "• 列出：「排程 列出」\n"
        "• 刪除：「排程 刪除 1」\n"
        "• 暫停：「排程 暫停 1」\n"
        "• 恢復：「排程 恢復 1」"
    )

    def __init__(self) -> None:
        self._path = config.data_dir() / "auto_schedules.json"
        self._schedules: list[ScheduleEntry] = []

    async def initialize(self) -> None:
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._schedules = [ScheduleEntry(**d) for d in data]
            except Exception:
                self._schedules = []

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([asdict(s) for s in self._schedules], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── Public API for ScheduleRunner ──────────────────────────────────────────

    def get_schedules(self) -> list[ScheduleEntry]:
        return self._schedules

    def update_last_run(self, sched_id: str, date_str: str) -> None:
        for s in self._schedules:
            if s.id == sched_id:
                s.last_run_date = date_str
                self._save()
                break

    # ── Skill entry point ───────────────────────────────────────────────────────

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()

        if any(k in text for k in ["列出", "list", "清單", "所有", "查看", "顯示"]):
            return self._list()
        elif any(k in text for k in ["刪除", "delete", "移除", "remove"]):
            return self._delete(query)
        elif any(k in text for k in ["暫停", "pause", "停止", "停用"]):
            return self._toggle(query, enabled=False)
        elif any(k in text for k in ["恢復", "resume", "啟用", "開啟", "繼續"]):
            return self._toggle(query, enabled=True)
        else:
            return self._add(query)

    # ── Operations ──────────────────────────────────────────────────────────────

    def _add(self, query: str) -> SkillResult:
        time_str, days_str, action = self._parse_schedule(query)

        if not time_str:
            return SkillResult(
                content=(
                    "⚠️ 無法解析排程時間。\n\n"
                    "請這樣說：\n"
                    "「每天早上6點 生成晨報」\n"
                    "「每週一早上8點 提醒我查看計劃」\n"
                    "「每個工作日下午5點 總結今日工作」"
                ),
                success=False, source=self.name,
            )
        if not action:
            return SkillResult(
                content="⚠️ 請說明要執行什麼任務，例如：「每天早上6點 生成晨報」",
                success=False, source=self.name,
            )

        sched_id = f"sched_{int(time.time())}"
        entry = ScheduleEntry(
            id=sched_id, name=action[:40],
            action=action, time=time_str, days=days_str,
        )
        self._schedules.append(entry)
        self._save()

        days_label = self._days_label(days_str)
        return SkillResult(
            content=(
                f"✅ **排程已建立**\n\n"
                f"📋 任務：{action}\n"
                f"⏰ 時間：{days_label} {time_str}\n"
                f"🔑 ID：`{sched_id}`\n\n"
                f"每次 Nexus 啟動時會自動恢復此排程，時間到會透過 Telegram 通知你。"
            ),
            success=True, source=self.name,
        )

    def _list(self) -> SkillResult:
        if not self._schedules:
            return SkillResult(content="📋 目前沒有循環排程。", success=True, source=self.name)

        lines = ["📋 **循環排程清單**\n"]
        for i, s in enumerate(self._schedules, 1):
            icon = "▶️" if s.enabled else "⏸️"
            days_label = self._days_label(s.days)
            last = f"（上次執行：{s.last_run_date}）" if s.last_run_date else "（尚未執行過）"
            lines.append(f"{icon} [{i}] {days_label} {s.time}\n    └ {s.name} {last}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _delete(self, query: str) -> SkillResult:
        idx = self._extract_index(query)
        if idx is None or not (0 <= idx < len(self._schedules)):
            return SkillResult(
                content="請指定要刪除的排程編號，例如：「排程 刪除 1」",
                success=False, source=self.name,
            )
        removed = self._schedules.pop(idx)
        self._save()
        return SkillResult(content=f"🗑️ 已刪除排程：{removed.name}", success=True, source=self.name)

    def _toggle(self, query: str, enabled: bool) -> SkillResult:
        idx = self._extract_index(query)
        if idx is None or not (0 <= idx < len(self._schedules)):
            return SkillResult(content="請指定排程編號", success=False, source=self.name)
        self._schedules[idx].enabled = enabled
        self._save()
        word = "恢復" if enabled else "暫停"
        icon = "▶️" if enabled else "⏸️"
        return SkillResult(
            content=f"{icon} 已{word}排程：{self._schedules[idx].name}",
            success=True, source=self.name,
        )

    # ── Parsing ─────────────────────────────────────────────────────────────────

    def _parse_schedule(self, text: str) -> tuple[str, str, str]:
        """Parse input into (time_str, days_str, action)."""

        # ── Days ──
        days = "daily"
        if re.search(r'工作日|平日|weekday', text):
            days = "weekdays"
        elif re.search(r'週末|假日|weekend', text):
            days = "weekends"
        else:
            # "每週一三五" style
            m = re.search(r'每週([一二三四五六日]+)', text)
            if m:
                pairs = [("一", "mon"), ("二", "tue"), ("三", "wed"), ("四", "thu"),
                         ("五", "fri"), ("六", "sat"), ("日", "sun")]
                codes = [code for ch, code in pairs if ch in m.group(1)]
                if codes:
                    days = ",".join(codes)
            else:
                # Single weekday "週一" / "星期一"
                pairs = [
                    (r"星期一|週一", "mon"), (r"星期二|週二", "tue"),
                    (r"星期三|週三", "wed"), (r"星期四|週四", "thu"),
                    (r"星期五|週五", "fri"), (r"星期六|週六", "sat"),
                    (r"星期日|週日|星期天", "sun"),
                ]
                codes = [code for pattern, code in pairs if re.search(pattern, text)]
                if codes:
                    days = ",".join(codes)

        # ── Time ──
        time_str = ""
        m = re.search(r'(上午|下午|早上|晚上)?\s*(\d{1,2})\s*[點:時](\d{0,2})', text)
        if m:
            period = m.group(1) or ""
            hour = int(m.group(2))
            minute = int(m.group(3)) if m.group(3) else 0
            if period in ("下午", "晚上") and hour < 12:
                hour += 12
            elif period in ("上午", "早上") and hour == 12:
                hour = 0
            time_str = f"{hour:02d}:{minute:02d}"

        # ── Action: remove all time/day keywords ──
        action = text
        for t in self.triggers:
            action = action.replace(t, "")
        action = re.sub(r'每[天日週]|每個工作日|每個週末|工作日|平日|週末|假日', '', action)
        action = re.sub(r'每週[一二三四五六日]+', '', action)
        action = re.sub(r'星期[一二三四五六日天]|週[一二三四五六日]', '', action)
        action = re.sub(r'(上午|下午|早上|晚上)?\s*\d{1,2}\s*[點:時]\d{0,2}', '', action)
        action = action.strip(" 的在：: ")

        return time_str, days, action

    def _extract_index(self, query: str) -> int | None:
        numbers = re.findall(r'\d+', query)
        if numbers:
            return int(numbers[-1]) - 1  # 1-indexed → 0-indexed
        return None

    def _days_label(self, days: str) -> str:
        if days in _DAYS_LABEL:
            return _DAYS_LABEL[days]
        parts = [_DAYS_LABEL.get(d.strip(), d.strip()) for d in days.split(",")]
        return "、".join(parts)
