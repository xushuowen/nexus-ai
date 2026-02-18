"""Weather skill using Open-Meteo API (100% free, no API key needed)."""

from __future__ import annotations

from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


# City name → lat/lon mapping (expandable)
CITIES = {
    "台北": (25.03, 121.57), "taipei": (25.03, 121.57),
    "高雄": (22.63, 120.30), "kaohsiung": (22.63, 120.30),
    "台中": (24.15, 120.67), "taichung": (24.15, 120.67),
    "東京": (35.68, 139.69), "tokyo": (35.68, 139.69),
    "大阪": (34.69, 135.50), "osaka": (34.69, 135.50),
    "紐約": (40.71, -74.01), "new york": (40.71, -74.01),
    "倫敦": (51.51, -0.13), "london": (51.51, -0.13),
    "首爾": (37.57, 126.98), "seoul": (37.57, 126.98),
    "北京": (39.90, 116.40), "beijing": (39.90, 116.40),
    "上海": (31.23, 121.47), "shanghai": (31.23, 121.47),
    "香港": (22.32, 114.17), "hong kong": (22.32, 114.17),
    "新加坡": (1.35, 103.82), "singapore": (1.35, 103.82),
}

WMO_CODES = {
    0: "晴天 ☀️", 1: "大致晴朗", 2: "多雲 ⛅", 3: "陰天 ☁️",
    45: "霧", 48: "霜霧", 51: "毛毛雨", 53: "中雨", 55: "大雨",
    61: "小雨 🌧️", 63: "中雨 🌧️", 65: "大雨 🌧️",
    71: "小雪 ❄️", 73: "中雪", 75: "大雪",
    80: "陣雨", 81: "中陣雨", 82: "大陣雨",
    95: "雷暴 ⛈️", 96: "雷暴+冰雹", 99: "強雷暴+冰雹",
}


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查詢全球城市天氣預報（免費，不需要 API key）"
    triggers = ["天氣", "weather", "幾度", "temperature", "下雨", "rain", "氣溫", "預報"]
    category = "utility"
    requires_llm = False

    instructions = "使用 Open-Meteo API 查詢天氣。解析用戶訊息找出城市名稱。"
    output_format = "城市: {city}\n溫度: {temp}°C\n天氣: {condition}\n濕度: {humidity}%"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        city_name, lat, lon = self._find_city(query)
        if not city_name:
            city_list = ", ".join(k for k in CITIES if not k.isascii())
            return SkillResult(
                content=f"找不到城市。支援的城市: {city_list}",
                success=False, source=self.name,
            )

        try:
            import httpx
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
                f"&timezone=auto"
            )
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()

            current = data.get("current", {})
            temp = current.get("temperature_2m", "N/A")
            humidity = current.get("relative_humidity_2m", "N/A")
            weather_code = current.get("weather_code", 0)
            wind = current.get("wind_speed_10m", "N/A")
            condition = WMO_CODES.get(weather_code, f"Code {weather_code}")

            result = (
                f"📍 {city_name} 天氣\n"
                f"🌡️ 溫度: {temp}°C\n"
                f"☁️ 天氣: {condition}\n"
                f"💧 濕度: {humidity}%\n"
                f"💨 風速: {wind} km/h"
            )
            return SkillResult(content=result, success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"天氣查詢失敗: {e}", success=False, source=self.name)

    def _find_city(self, query: str) -> tuple[str | None, float, float]:
        query_lower = query.lower()
        for city, (lat, lon) in CITIES.items():
            if city in query_lower:
                display = city if not city.isascii() else city.title()
                return display, lat, lon
        return None, 0, 0
