"""Local calendar management tool using .ics format."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from nexus.tools.tool_base import BaseTool, ToolParameter, ToolResult
from nexus import config


class CalendarTool(BaseTool):
    name = "calendar"
    description = "Manage local calendar events (add, list, remove)"
    category = "productivity"
    parameters = [
        ToolParameter("action", "string", "Action: 'add', 'list', 'remove'",
                       enum=["add", "list", "remove"]),
        ToolParameter("title", "string", "Event title", required=False),
        ToolParameter("date", "string", "Date in YYYY-MM-DD format", required=False),
        ToolParameter("time", "string", "Time in HH:MM format", required=False),
        ToolParameter("event_id", "string", "Event ID for removal", required=False),
    ]

    def __init__(self) -> None:
        self._events_path = config.data_dir() / "calendar.json"

    def _load_events(self) -> list[dict[str, Any]]:
        if self._events_path.exists():
            return json.loads(self._events_path.read_text(encoding="utf-8"))
        return []

    def _save_events(self, events: list[dict]) -> None:
        self._events_path.write_text(json.dumps(events, indent=2), encoding="utf-8")

    async def execute(self, **kwargs) -> ToolResult:
        action = kwargs.get("action", "list")

        if action == "list":
            events = self._load_events()
            if not events:
                return ToolResult(success=True, output="No calendar events.")
            lines = []
            for e in sorted(events, key=lambda x: x.get("date", "")):
                lines.append(f"[{e['id']}] {e['date']} {e.get('time', '')} - {e['title']}")
            return ToolResult(success=True, output="\n".join(lines))

        elif action == "add":
            title = kwargs.get("title", "Untitled")
            date = kwargs.get("date", datetime.now().strftime("%Y-%m-%d"))
            time_str = kwargs.get("time", "")
            events = self._load_events()
            event_id = f"evt_{int(time.time())}"
            events.append({"id": event_id, "title": title, "date": date, "time": time_str})
            self._save_events(events)
            return ToolResult(success=True, output=f"Added event '{title}' on {date} {time_str}")

        elif action == "remove":
            event_id = kwargs.get("event_id", "")
            events = self._load_events()
            events = [e for e in events if e.get("id") != event_id]
            self._save_events(events)
            return ToolResult(success=True, output=f"Removed event {event_id}")

        return ToolResult(success=False, output="", error="Unknown action")
