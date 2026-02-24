"""Currency exchange skill - free open exchange rates API (no key needed)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

# Common currency aliases
CURRENCY_ALIASES: dict[str, str] = {
    # Traditional Chinese
    "台幣": "TWD", "新台幣": "TWD", "台元": "TWD",
    "美金": "USD", "美元": "USD", "美刀": "USD",
    "日圓": "JPY", "日元": "JPY", "日幣": "JPY",
    "歐元": "EUR", "歐幣": "EUR",
    "港幣": "HKD", "港元": "HKD",
    "人民幣": "CNY", "大陸幣": "CNY", "rmb": "CNY",
    "英鎊": "GBP",
    "韓元": "KRW", "韓圜": "KRW",
    "澳幣": "AUD", "澳元": "AUD",
    "加幣": "CAD", "加元": "CAD",
    "瑞士法郎": "CHF", "法郎": "CHF",
    "新加坡幣": "SGD", "新幣": "SGD",
    "泰銖": "THB",
    "越南盾": "VND",
    "馬幣": "MYR",
    "印尼盾": "IDR",
    "菲律賓披索": "PHP", "披索": "PHP",
    # ISO codes (lowercase)
    "twd": "TWD", "usd": "USD", "eur": "EUR", "jpy": "JPY", "gbp": "GBP",
    "hkd": "HKD", "cny": "CNY", "krw": "KRW", "aud": "AUD", "cad": "CAD",
    "chf": "CHF", "sgd": "SGD", "thb": "THB", "vnd": "VND", "myr": "MYR",
    "idr": "IDR", "php": "PHP",
}

CURRENCY_NAMES: dict[str, str] = {
    "TWD": "新台幣", "USD": "美元", "EUR": "歐元", "JPY": "日圓",
    "GBP": "英鎊", "HKD": "港幣", "CNY": "人民幣", "KRW": "韓元",
    "AUD": "澳幣", "CAD": "加幣", "CHF": "瑞士法郎", "SGD": "新加坡幣",
    "THB": "泰銖", "VND": "越南盾", "MYR": "馬幣", "IDR": "印尼盾",
    "PHP": "菲律賓披索",
}


class CurrencySkill(BaseSkill):
    name = "currency"
    description = "即時匯率換算 — 免費 API，支援 170+ 幣別（USD、TWD、JPY 等）"
    triggers = [
        "匯率", "換算", "兌換", "currency", "exchange rate",
        "美金換", "台幣換", "日圓換", "歐元換",
    ]
    intent_patterns = [
        r"\d+\s*(美金|台幣|日圓|歐元|英鎊|港幣|人民幣|韓元|澳幣|加幣|新加坡幣|泰銖)",
        r"(美金|台幣|日圓|歐元|英鎊|USD|TWD|JPY|EUR|GBP).{0,10}(換|兌換|等於|值多少|是多少).{0,10}(美金|台幣|日圓|歐元|英鎊|USD|TWD|JPY|EUR|GBP)",
        r"(匯率|exchange rate).{0,15}(美金|台幣|日圓|歐元|USD|TWD|JPY|EUR)",
        r"\d+\s*(USD|TWD|JPY|EUR|GBP|HKD|CNY|KRW|AUD|CAD|CHF|SGD)",
        r"(今天|現在|目前).{0,5}(匯率|匯价|兌換率)",
        r"(換|兌換)\s*\d+\s*(美金|台幣|日圓|歐元)",
        r"(how much|how many).{0,10}(USD|TWD|JPY|EUR|GBP|dollars|yen|euros)",
    ]
    category = "finance"
    requires_llm = False

    instructions = (
        "匯率換算：\n"
        "1. 「100 美金換台幣」\n"
        "2. 「1 USD to TWD」\n"
        "3. 「今天美金匯率」\n"
        "4. 「500 日圓等於多少台幣」"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        amount, from_cur, to_cur = self._parse_query(query)

        if not from_cur:
            return SkillResult(
                content=(
                    "請提供換算資訊，例如：\n"
                    "• 「100 美金換台幣」\n"
                    "• 「1 USD to TWD」\n"
                    "• 「今天美金匯率」"
                ),
                success=False, source=self.name,
            )

        return await self._fetch_rate(amount, from_cur, to_cur or "TWD")

    def _parse_query(self, text: str) -> tuple[float, str | None, str | None]:
        """Parse amount, from_currency, to_currency from natural language."""
        amount = 1.0
        from_cur = None
        to_cur = None

        # Extract amount
        m = re.search(r'(\d+(?:,\d{3})*(?:\.\d+)?)', text.replace(",", ""))
        if m:
            try:
                amount = float(m.group(1).replace(",", ""))
            except ValueError:
                amount = 1.0

        text_lower = text.lower()

        # Find currencies in order of appearance
        found_currencies = []
        positions = []
        for alias, code in CURRENCY_ALIASES.items():
            idx = text_lower.find(alias.lower())
            if idx >= 0:
                positions.append((idx, code))

        # Also check ISO codes directly
        for code in ["USD", "TWD", "EUR", "JPY", "GBP", "HKD", "CNY", "KRW",
                     "AUD", "CAD", "CHF", "SGD", "THB", "MYR"]:
            idx = text_lower.find(code.lower())
            if idx >= 0:
                positions.append((idx, code))

        # Sort by position in text
        positions.sort(key=lambda x: x[0])
        seen = []
        for _, code in positions:
            if code not in seen:
                seen.append(code)

        if len(seen) >= 2:
            from_cur, to_cur = seen[0], seen[1]
        elif len(seen) == 1:
            from_cur = seen[0]

        return amount, from_cur, to_cur

    async def _fetch_rate(self, amount: float, from_cur: str, to_cur: str) -> SkillResult:
        """Fetch exchange rate using open.er-api.com (free, no key needed)."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://open.er-api.com/v6/latest/{from_cur}",
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("result") != "success":
                raise ValueError(f"API error: {data.get('error-type', 'unknown')}")

            rates = data.get("rates", {})
            if to_cur not in rates:
                return SkillResult(
                    content=f"找不到幣別「{to_cur}」，請確認代碼。",
                    success=False, source=self.name,
                )

            rate = rates[to_cur]
            converted = amount * rate
            update_time = data.get("time_last_update_utc", "N/A")[:16]

            from_name = CURRENCY_NAMES.get(from_cur, from_cur)
            to_name = CURRENCY_NAMES.get(to_cur, to_cur)

            # Format numbers nicely
            if converted > 10000:
                converted_str = f"{converted:,.2f}"
            elif converted < 0.01:
                converted_str = f"{converted:.6f}"
            else:
                converted_str = f"{converted:.4f}"

            if amount == 1.0:
                rate_line = f"💱 **1 {from_cur} = {rate:.4f} {to_cur}**"
            else:
                amt_str = f"{amount:,.0f}" if amount.is_integer() else f"{amount:,.2f}"
                rate_line = f"💱 **{amt_str} {from_cur} = {converted_str} {to_cur}**"

            lines = [
                rate_line,
                f"   {from_name} → {to_name}",
                f"   匯率：1 {from_cur} = {rate:.4f} {to_cur}",
                f"   更新：{update_time} UTC",
            ]

            # Show common conversions if only checking rate
            if amount == 1.0:
                common = [100, 500, 1000]
                lines.append(f"\n📊 常用換算（{from_cur} → {to_cur}）：")
                for v in common:
                    lines.append(f"   {v:,} {from_cur} = {v * rate:,.2f} {to_cur}")

            return SkillResult(
                content="\n".join(lines),
                success=True, source=self.name,
                metadata={"from": from_cur, "to": to_cur, "rate": rate},
            )

        except httpx.TimeoutException:
            return SkillResult(content="匯率查詢超時，請稍後再試。", success=False, source=self.name)
        except Exception as e:
            return SkillResult(content=f"匯率查詢失敗: {e}", success=False, source=self.name)
