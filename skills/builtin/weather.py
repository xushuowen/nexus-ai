"""Weather skill using wttr.in (OpenClaw style - free, no API key, any city)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查詢全球任意城市天氣預報（wttr.in，免費）"
    triggers = ["天氣", "weather", "幾度", "temperature", "下雨", "rain", "氣溫", "預報", "forecast"]
    category = "utility"
    requires_llm = False

    instructions = "使用 wttr.in API 查詢天氣。支援全球任意城市。"
    output_format = "城市: {city}\n溫度: {temp}°C\n天氣: {condition}\n濕度: {humidity}%"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        city = self._extract_city(query)
        if not city:
            return SkillResult(
                content="請提供城市名稱，例如：「天氣 台北」或「weather Tokyo」",
                success=False, source=self.name,
            )

        try:
            import httpx
            url = f"https://wttr.in/{city}?format=j1"
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Nexus-AI/1.0"})
                resp.raise_for_status()
                data = resp.json()

            current = data.get("current_condition", [{}])[0]
            area = data.get("nearest_area", [{}])[0]

            temp_c = current.get("temp_C", "N/A")
            feels_like = current.get("FeelsLikeC", "N/A")
            humidity = current.get("humidity", "N/A")
            wind_speed = current.get("windspeedKmph", "N/A")
            wind_dir = current.get("winddir16Point", "")
            desc_zh = current.get("lang_zh-tw", [{}])
            if isinstance(desc_zh, list) and desc_zh:
                condition = desc_zh[0].get("value", "")
            else:
                condition = current.get("weatherDesc", [{}])[0].get("value", "N/A")

            city_name = area.get("areaName", [{}])[0].get("value", city) if area.get("areaName") else city
            country = area.get("country", [{}])[0].get("value", "") if area.get("country") else ""

            # Forecast
            forecast_lines = []
            for day in data.get("weather", [])[:3]:
                date = day.get("date", "")
                max_t = day.get("maxtempC", "")
                min_t = day.get("mintempC", "")
                desc = day.get("hourly", [{}])[4].get("weatherDesc", [{}])[0].get("value", "") if day.get("hourly") else ""
                forecast_lines.append(f"  {date}: {min_t}~{max_t}°C {desc}")

            result = (
                f"📍 {city_name}"
                + (f", {country}" if country else "")
                + f"\n🌡️ 溫度: {temp_c}°C（體感 {feels_like}°C）"
                f"\n☁️ 天氣: {condition}"
                f"\n💧 濕度: {humidity}%"
                f"\n💨 風速: {wind_speed} km/h {wind_dir}"
            )
            if forecast_lines:
                result += "\n\n📅 三日預報:\n" + "\n".join(forecast_lines)

            return SkillResult(content=result, success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"天氣查詢失敗: {e}", success=False, source=self.name)

    def _extract_city(self, query: str) -> str:
        """Extract city name from query by removing trigger words."""
        text = query
        for t in self.triggers:
            text = re.sub(re.escape(t), "", text, flags=re.IGNORECASE)
        text = text.strip(" ?？，,。.")
        return text if len(text) >= 1 else ""
