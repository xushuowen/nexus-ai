"""Weather skill using Open-Meteo + Geocoding API (free, no API key required)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

# WMO weather code descriptions (zh-TW)
WMO_CODES = {
    0: "晴天☀️", 1: "大致晴朗🌤️", 2: "部分多雲⛅", 3: "陰天☁️",
    45: "有霧🌫️", 48: "冰霧🌫️",
    51: "毛毛雨🌦️", 53: "毛毛雨🌦️", 55: "濃毛毛雨🌧️",
    61: "小雨🌧️", 63: "中雨🌧️", 65: "大雨🌧️",
    71: "小雪❄️", 73: "中雪❄️", 75: "大雪❄️",
    77: "冰晶❄️",
    80: "陣雨🌦️", 81: "中陣雨🌧️", 82: "強陣雨⛈️",
    85: "陣雪❄️", 86: "強陣雪❄️",
    95: "雷雨⛈️", 96: "冰雹雷雨⛈️", 99: "強冰雹雷雨⛈️",
}


class WeatherSkill(BaseSkill):
    name = "weather"
    description = "查詢全球任意城市天氣預報（Open-Meteo，免費，免 API Key）"
    triggers = ["天氣", "weather", "幾度", "temperature", "下雨", "rain", "氣溫", "預報", "forecast"]
    intent_patterns = [
        r"(今天|明天|這週|這幾天).{0,10}(冷|熱|涼|穿什麼|帶傘)",
        r"要(帶傘|穿外套|穿厚|穿薄)",
        r"(冷嗎|熱嗎|會下雨嗎|需要帶傘嗎)",
        r"(出門|外出).{0,10}(要帶|需要|穿)",
    ]
    category = "utility"
    requires_llm = False
    instructions = "使用 Open-Meteo 查詢天氣，支援全球城市，免 API Key。"

    _FILLER = [
        "今天", "明天", "這週", "這幾天", "現在", "查一下", "幫我查", "查詢",
        "怎麼樣", "如何", "狀況", "情況", "怎樣", "呢", "嗎", "啊", "吧",
        "的", "是", "有", "會", "要",
    ]

    _CITY_MAP = {
        "台北": "Taipei", "臺北": "Taipei", "新北": "New Taipei",
        "台中": "Taichung", "臺中": "Taichung", "台南": "Tainan", "臺南": "Tainan",
        "高雄": "Kaohsiung", "桃園": "Taoyuan", "新竹": "Hsinchu",
        "基隆": "Keelung", "花蓮": "Hualien", "台東": "Taitung",
        "嘉義": "Chiayi", "彰化": "Changhua", "南投": "Nantou",
        "宜蘭": "Yilan", "屏東": "Pingtung", "澎湖": "Penghu",
    }

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        city = self._extract_city(query)
        if not city:
            return SkillResult(
                content="請提供城市名稱，例如：「台北天氣」或「weather Tokyo」",
                success=False, source=self.name,
            )
        return await self._fetch_weather(city)

    async def _fetch_weather(self, city: str) -> SkillResult:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
                # Step 1: Geocoding — get lat/lon
                geo_resp = await client.get(
                    "https://geocoding-api.open-meteo.com/v1/search",
                    params={"name": city, "count": 1, "language": "zh", "format": "json"},
                )
                geo_resp.raise_for_status()
                geo = geo_resp.json().get("results", [])
                if not geo:
                    return SkillResult(
                        content=f"找不到城市「{city}」，請確認拼寫（例如：Taipei、Tokyo、London）",
                        success=False, source=self.name,
                    )

                loc = geo[0]
                lat = loc["latitude"]
                lon = loc["longitude"]
                city_name = loc.get("name", city)
                country = loc.get("country", "")
                admin = loc.get("admin1", "")

                # Step 2: Weather — current + 3-day forecast
                wx_resp = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat, "longitude": lon,
                        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,precipitation",
                        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                        "timezone": "auto",
                        "forecast_days": 4,
                    },
                )
                wx_resp.raise_for_status()
                wx = wx_resp.json()

            cur = wx.get("current", {})
            temp = cur.get("temperature_2m", "N/A")
            feels = cur.get("apparent_temperature", "N/A")
            humidity = cur.get("relative_humidity_2m", "N/A")
            wind_spd = cur.get("wind_speed_10m", "N/A")
            precip = cur.get("precipitation", 0)
            wmo = cur.get("weather_code", 0)
            condition = WMO_CODES.get(wmo, f"代碼 {wmo}")

            location_str = city_name
            if admin and admin != city_name:
                location_str += f", {admin}"
            if country:
                location_str += f", {country}"

            lines = [
                f"📍 **{location_str}**",
                f"🌡️ 溫度: **{temp}°C**（體感 {feels}°C）",
                f"☁️ 天氣: {condition}",
                f"💧 濕度: {humidity}%",
                f"💨 風速: {wind_spd} km/h",
            ]
            if precip and float(precip) > 0:
                lines.append(f"🌧️ 降水: {precip} mm")

            # 3-day forecast
            daily = wx.get("daily", {})
            dates = daily.get("time", [])
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])

            if dates:
                lines.append("\n📅 **三日預報:**")
                for i in range(min(3, len(dates))):
                    d_condition = WMO_CODES.get(codes[i] if i < len(codes) else 0, "")
                    lines.append(
                        f"  {dates[i]}: {min_temps[i] if i < len(min_temps) else '?'}~"
                        f"{max_temps[i] if i < len(max_temps) else '?'}°C {d_condition}"
                    )

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"天氣查詢失敗: {e}", success=False, source=self.name)

    def _extract_city(self, query: str) -> str:
        """Extract city name, strip triggers and filler words."""
        text = query
        for t in self.triggers:
            text = re.sub(re.escape(t), "", text, flags=re.IGNORECASE)
        for f in self._FILLER:
            text = text.replace(f, "")
        text = text.strip(" ?？，,。.、！!　\t\n")
        return self._CITY_MAP.get(text, text) if text else ""
