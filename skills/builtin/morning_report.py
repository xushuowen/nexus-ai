"""Morning Report Skill — 每日晨報：台北天氣 + 國際新聞 + 今日排程。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

_WMO = {
    0: "晴☀️", 1: "大致晴🌤️", 2: "多雲⛅", 3: "陰☁️",
    45: "霧🌫️", 51: "毛毛雨🌦️", 53: "毛毛雨🌦️", 55: "大毛毛雨🌧️",
    61: "小雨🌧️", 63: "中雨🌧️", 65: "大雨🌧️",
    71: "小雪❄️", 73: "中雪❄️", 75: "大雪❄️",
    80: "陣雨🌦️", 81: "中陣雨🌧️", 82: "強陣雨⛈️",
    95: "雷雨⛈️", 99: "強冰雹雷雨⛈️",
}

_RSS_FEEDS = [
    ("BBC World",  "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("WHO Health",  "https://www.who.int/rss-feeds/news-english.xml"),
]


class MorningReportSkill(BaseSkill):
    name = "morning_report"
    description = "每日晨報 — 台北天氣 + 國際新聞 + 今日排程，免 API Key"
    triggers = [
        "晨報", "morning report", "生成晨報", "今日晨報",
        "每日摘要", "早安摘要", "早報", "今日摘要",
    ]
    intent_patterns = [
        r"生成.{0,5}(晨報|早報|日報|摘要)",
        r"(今日|每日|早上|今天).{0,5}(摘要|晨報|報告|簡報)",
        r"(幫我|給我).{0,5}(晨報|早報|今日摘要|今天摘要)",
    ]
    category = "productivity"
    requires_llm = False

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        now = datetime.now()
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        date_str = f"{now.month}月{now.day}日（星期{weekdays[now.weekday()]}）"

        weather_text  = await self._fetch_weather()
        news_text     = await self._fetch_news()
        schedule_text = self._get_schedules()

        sections = [
            f"## ☀️ Nexus 晨報 · {date_str}\n",
            f"### 🌡️ 台北天氣\n{weather_text}",
            f"### 📰 今日要聞\n{news_text}",
        ]
        if schedule_text:
            sections.append(f"### 📅 今日排程\n{schedule_text}")
        sections.append("\n---\n*Powered by Gemini · Nexus AI*")

        return SkillResult(
            content="\n\n".join(sections),
            success=True,
            source=self.name,
        )

    # ── Weather ─────────────────────────────────────────────────────────────────

    async def _fetch_weather(self) -> str:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                geo = (await c.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": "Taipei", "count": 1, "language": "zh", "format": "json"},
                )).json().get("results", [])
                if not geo:
                    return "⚠️ 天氣查詢失敗"
                lat, lon = geo[0]["latitude"], geo[0]["longitude"]
                wx = (await c.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,apparent_temperature,weather_code,precipitation,relative_humidity_2m",
                        "timezone": "auto",
                    },
                )).json()
            cur = wx.get("current", {})
            temp   = cur.get("temperature_2m", "?")
            feels  = cur.get("apparent_temperature", "?")
            humid  = cur.get("relative_humidity_2m", "?")
            cond   = _WMO.get(cur.get("weather_code", 0), "")
            precip = cur.get("precipitation", 0)
            result = f"{cond} **{temp}°C**（體感 {feels}°C）· 濕度 {humid}%"
            try:
                if precip and float(precip) > 0:
                    result += f" · 降水 {precip}mm"
            except (TypeError, ValueError):
                pass
            return result
        except Exception as e:
            return f"⚠️ 天氣取得失敗: {e}"

    # ── News ────────────────────────────────────────────────────────────────────

    async def _fetch_news(self) -> str:
        try:
            import httpx
            articles = []
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
                for source, url in _RSS_FEEDS:
                    try:
                        resp = await c.get(url, headers={"User-Agent": "Nexus-AI/1.0"})
                        titles = re.findall(r'<title[^>]*>(.*?)</title>', resp.text, re.DOTALL)
                        for title in titles[1:3]:  # skip feed title, take 2 per source
                            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title).strip()
                            title = re.sub(r'<[^>]+>', '', title).strip()
                            if title:
                                articles.append(f"- **[{source}]** {title}")
                    except Exception:
                        continue
            return "\n".join(articles) if articles else "⚠️ 新聞取得失敗"
        except Exception as e:
            return f"⚠️ 新聞取得失敗: {e}"

    # ── Schedule ────────────────────────────────────────────────────────────────

    def _get_schedules(self) -> str:
        try:
            from nexus import config
            path = config.data_dir() / "auto_schedules.json"
            if not path.exists():
                return ""
            data = json.loads(path.read_text(encoding="utf-8"))
            now = datetime.now()
            weekdays_en = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            today = weekdays_en[now.weekday()]
            is_weekday = now.weekday() < 5
            lines = []
            for s in data:
                if not s.get("enabled", True):
                    continue
                d = s.get("days", "daily")
                if (d == "daily"
                        or (d == "weekdays" and is_weekday)
                        or (d == "weekends" and not is_weekday)
                        or today in d.split(",")):
                    lines.append(f"⏰ {s.get('time', '--:--')}  {s.get('name', '')}")
            return "\n".join(lines) if lines else "今日無排程"
        except Exception:
            return ""
