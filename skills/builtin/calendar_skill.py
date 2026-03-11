"""Google Calendar skill — 讀取/新增行程，整合到個人 AI 助理。

Setup (one-time):
    1. 到 https://console.cloud.google.com → 建立專案 → 啟用 Calendar API
    2. 建立 OAuth 2.0 憑證（Desktop App）→ 下載 credentials.json
    3. 放到 nexus/data/google_credentials.json
    4. 第一次使用時會開啟瀏覽器讓你授權，之後自動記住
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from nexus import config
from nexus.skills.skill_base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)

_CREDS_FILE   = config.data_dir() / "google_credentials.json"
_TOKEN_FILE   = config.data_dir() / "google_calendar_token.json"
_SCOPES       = ["https://www.googleapis.com/auth/calendar"]
_SETUP_MSG    = (
    "尚未設定 Google Calendar 授權。\n\n"
    "設定步驟：\n"
    "1. 前往 https://console.cloud.google.com\n"
    "2. 建立專案 → API和服務 → 啟用 Google Calendar API\n"
    "3. 憑證 → 建立 OAuth 2.0 用戶端 ID（桌面應用程式）→ 下載 JSON\n"
    "4. 將下載的檔案重新命名為 google_credentials.json\n"
    "5. 放到 nexus/data/ 資料夾\n"
    "6. 再說一次你的行程問題，會自動開啟瀏覽器授權。"
)


def _get_service():
    """Build and return an authorized Google Calendar service object."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "缺少必要套件，請執行: pip install google-api-python-client google-auth-oauthlib"
        )

    creds = None
    if _TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(_TOKEN_FILE), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not _CREDS_FILE.exists():
                raise FileNotFoundError("google_credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS_FILE), _SCOPES)
            creds = flow.run_local_server(port=0)
        _TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds)


def _parse_date_from_query(text: str) -> tuple[datetime, datetime]:
    """Parse time range from natural language query. Returns (start, end) in local time."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "今天" in text or "今日" in text:
        return today_start, today_start + timedelta(days=1)
    if "明天" in text or "明日" in text:
        d = today_start + timedelta(days=1)
        return d, d + timedelta(days=1)
    if "後天" in text:
        d = today_start + timedelta(days=2)
        return d, d + timedelta(days=1)
    if "本週" in text or "這週" in text or "這周" in text:
        monday = today_start - timedelta(days=now.weekday())
        return monday, monday + timedelta(days=7)
    if "下週" in text or "下周" in text:
        monday = today_start - timedelta(days=now.weekday()) + timedelta(weeks=1)
        return monday, monday + timedelta(days=7)
    if "本月" in text or "這個月" in text:
        start = today_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end

    # Default: next 7 days
    return today_start, today_start + timedelta(days=7)


def _format_events(events: list[dict]) -> str:
    """Format a list of Google Calendar event dicts into readable text."""
    if not events:
        return "這段時間沒有行程。"
    lines = []
    for ev in events:
        start = ev.get("start", {})
        dt_str = start.get("dateTime") or start.get("date", "")
        summary = ev.get("summary", "（無標題）")
        location = ev.get("location", "")
        if "T" in dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                dt_local = dt.astimezone()
                time_str = dt_local.strftime("%m/%d %H:%M")
            except Exception:
                time_str = dt_str
        else:
            time_str = dt_str
        line = f"• {time_str} — {summary}"
        if location:
            line += f" [{location}]"
        lines.append(line)
    return "\n".join(lines)


def _parse_new_event(text: str) -> dict | None:
    """Try to extract event title and time from natural language for quick creation."""
    # Patterns: "明天下午3點 開會" / "加一個 明天 14:00 的 meeting"
    time_patterns = [
        r'(今天|明天|後天|[\d/]+)[^\d]*(\d{1,2})[點:：](\d{0,2})\s*(.+)',
        r'(.+?)\s+(\d{1,2})[點:：](\d{0,2})',
    ]
    for pat in time_patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)  # raw match for LLM to parse
    return None


class CalendarSkill(BaseSkill):
    name = "calendar"
    description = "查詢或新增 Google Calendar 行程"
    category = "productivity"
    requires_llm = True

    triggers = [
        "行程", "日曆", "calendar", "會議", "今天有什麼", "明天有什麼",
        "本週行程", "下週行程", "加一個會議", "新增行程", "安排時間",
        "schedule", "event", "appointment", "幫我約", "幫我排",
        "查行程", "看行程",
    ]
    intent_patterns = [
        r'(今天|明天|後天|本週|這週|下週).{0,10}(行程|會議|安排|有什麼)',
        r'(幫我|請幫).{0,10}(加|新增|建立|排).{0,10}(行程|會議|活動)',
        r'(查|看|有沒有).{0,10}(行程|會議|活動)',
    ]
    synonyms = {
        "行程": ["待辦", "安排", "日程"],
        "會議": ["meet", "meeting", "開會"],
    }

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Check credentials exist
        if not _CREDS_FILE.exists() and not _TOKEN_FILE.exists():
            return SkillResult(content=_SETUP_MSG, success=False, source="calendar")

        is_create = any(kw in query for kw in ["加", "新增", "建立", "排", "約", "create", "add"])

        try:
            service = _get_service()
        except FileNotFoundError:
            return SkillResult(content=_SETUP_MSG, success=False, source="calendar")
        except RuntimeError as e:
            return SkillResult(content=str(e), success=False, source="calendar")
        except Exception as e:
            logger.error("Calendar auth error: %s", e)
            return SkillResult(
                content=f"Google Calendar 授權失敗：{e}", success=False, source="calendar"
            )

        if is_create:
            return await self._create_event(service, query, context)
        else:
            return await self._list_events(service, query)

    async def _list_events(self, service, query: str) -> SkillResult:
        start, end = _parse_date_from_query(query)
        tz_offset = datetime.now(timezone.utc).astimezone().utcoffset()
        tz_str = f"{int(tz_offset.total_seconds()//3600):+03d}:00"

        start_iso = start.isoformat() + tz_str
        end_iso   = end.isoformat() + tz_str

        try:
            result = service.events().list(
                calendarId="primary",
                timeMin=start_iso,
                timeMax=end_iso,
                maxResults=20,
                singleEvents=True,
                orderBy="startTime",
            ).execute()
            events = result.get("items", [])
            text = _format_events(events)
            label = start.strftime("%m/%d") if start.date() != end.date() - timedelta(days=1) else start.strftime("%m/%d")
            return SkillResult(
                content=f"**行程（{start.strftime('%m/%d')} ～ {(end-timedelta(days=1)).strftime('%m/%d')}）**\n\n{text}",
                success=True,
                source="calendar",
                metadata={"event_count": len(events)},
            )
        except Exception as e:
            logger.error("Calendar list error: %s", e)
            return SkillResult(content=f"讀取行程失敗：{e}", success=False, source="calendar")

    async def _create_event(self, service, query: str, context: dict) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(
                content="需要 LLM 協助解析行程資訊，目前無法使用。",
                success=False, source="calendar"
            )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        parse_prompt = (
            f"現在時間：{now_str}\n"
            f"使用者說：「{query}」\n\n"
            "請從這段話提取行程資訊，以 JSON 格式回傳：\n"
            '{"title": "行程標題", "start": "YYYY-MM-DDTHH:MM:00", '
            '"end": "YYYY-MM-DDTHH:MM:00", "location": "地點或空字串"}\n'
            "如果時間不明確，start 預設為明天同一時段 +1小時，end = start + 1小時。\n"
            "只回傳 JSON，不要其他文字。"
        )
        try:
            raw = await llm.complete(parse_prompt, task_type="general", source="calendar_parse")
            # Extract JSON from response
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                raise ValueError("No JSON found in LLM response")
            ev_data = json.loads(m.group(0))
        except Exception as e:
            return SkillResult(
                content=f"無法解析行程資訊：{e}\n請更明確說明時間，例如：「幫我加明天下午3點的開會」",
                success=False, source="calendar"
            )

        tz_str = datetime.now(timezone.utc).astimezone().strftime("%z")
        tz_formatted = f"{tz_str[:3]}:{tz_str[3:]}"

        event_body = {
            "summary": ev_data.get("title", "新行程"),
            "start": {"dateTime": ev_data["start"] + tz_formatted, "timeZone": "Asia/Taipei"},
            "end":   {"dateTime": ev_data["end"]   + tz_formatted, "timeZone": "Asia/Taipei"},
        }
        if ev_data.get("location"):
            event_body["location"] = ev_data["location"]

        try:
            created = service.events().insert(calendarId="primary", body=event_body).execute()
            link = created.get("htmlLink", "")
            return SkillResult(
                content=(
                    f"行程已建立！\n\n"
                    f"• 標題：{event_body['summary']}\n"
                    f"• 時間：{ev_data['start'].replace('T', ' ')}\n"
                    f"• 結束：{ev_data['end'].replace('T', ' ')}\n"
                    + (f"• 地點：{ev_data['location']}\n" if ev_data.get('location') else "")
                    + (f"\n[查看行程]({link})" if link else "")
                ),
                success=True,
                source="calendar",
            )
        except Exception as e:
            logger.error("Calendar create error: %s", e)
            return SkillResult(content=f"建立行程失敗：{e}", success=False, source="calendar")
