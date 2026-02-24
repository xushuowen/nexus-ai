"""Stock price skill - Yahoo Finance unofficial API (free, no key needed)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

# Common stock symbol aliases (zh → ticker)
STOCK_ALIASES: dict[str, str] = {
    # US Tech
    "蘋果": "AAPL", "apple": "AAPL",
    "微軟": "MSFT", "microsoft": "MSFT",
    "谷歌": "GOOGL", "google": "GOOGL", "alphabet": "GOOGL",
    "亞馬遜": "AMZN", "amazon": "AMZN",
    "特斯拉": "TSLA", "tesla": "TSLA",
    "輝達": "NVDA", "nvidia": "NVDA",
    "meta": "META", "facebook": "META",
    "netflix": "NFLX", "奈飛": "NFLX",
    "AMD": "AMD", "amd": "AMD",
    "英特爾": "INTC", "intel": "INTC",
    # Taiwan stocks (append .TW)
    "台積電": "TSM",  # US-listed ADR
    "鴻海": "2317.TW",
    "聯發科": "2454.TW",
    "台達電": "2308.TW",
    "富邦金": "2881.TW",
    "國泰金": "2882.TW",
    # ETFs
    "QQQ": "QQQ", "SPY": "SPY", "VOO": "VOO",
    "標普500": "SPY", "那斯達克": "QQQ",
    # Crypto (Yahoo Finance supports these)
    "比特幣": "BTC-USD", "bitcoin": "BTC-USD", "btc": "BTC-USD",
    "以太幣": "ETH-USD", "ethereum": "ETH-USD", "eth": "ETH-USD",
    "狗狗幣": "DOGE-USD", "dogecoin": "DOGE-USD",
}

# Change indicators
_ARROW_UP = "📈"
_ARROW_DOWN = "📉"
_FLAT = "➡️"


class StockSkill(BaseSkill):
    name = "stock"
    description = "股票行情 — 即時股價查詢（美股、台股、ETF、加密貨幣，免費）"
    triggers = [
        "股票", "股價", "stock", "股市", "漲跌",
        "AAPL", "TSLA", "NVDA", "MSFT", "GOOGL",
        "台積電", "漲了多少", "跌了多少",
    ]
    intent_patterns = [
        r"(查|看|查一下|看一下).{0,10}(股價|股票|行情|漲跌|收盤價|開盤|報價)",
        r"(蘋果|微軟|特斯拉|輝達|谷歌|亞馬遜|台積電|聯發科).{0,10}(股票|股價|現在|漲跌|今天|報價)",
        r"[A-Z]{1,5}\s*(stock|share|price|現在|股價|報價)",
        r"\d{4}\.TW.{0,10}(股價|多少|報價|漲跌)",
        r"(比特幣|以太幣|BTC|ETH|bitcoin|ethereum).{0,10}(多少|價格|現在|行情|漲跌)",
        r"(今天|最近|現在).{0,5}(股市|大盤|指數|美股|台股).{0,5}(怎麼樣|如何|漲跌|情況)",
        r"(SPY|QQQ|VOO|標普|那斯達克).{0,10}(多少|今天|漲跌|報價)",
    ]
    category = "finance"
    requires_llm = False

    instructions = (
        "股票查詢：\n"
        "1. 美股：「蘋果股價」「AAPL」「特斯拉今天漲跌」\n"
        "2. 台股：「台積電股價」「2330.TW」\n"
        "3. ETF：「SPY 報價」「QQQ 今天」\n"
        "4. 加密貨幣：「比特幣現在多少」「ETH 價格」"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        symbols = self._extract_symbols(query)

        if not symbols:
            return SkillResult(
                content=(
                    "請提供股票代碼或名稱，例如：\n"
                    "• 「蘋果股價」「AAPL」\n"
                    "• 「台積電」「2330.TW」\n"
                    "• 「比特幣」「BTC-USD」"
                ),
                success=False, source=self.name,
            )

        results = []
        for symbol in symbols[:3]:  # Limit to 3 at once
            result = await self._fetch_quote(symbol)
            results.append(result)

        combined = "\n\n".join(r.content for r in results)
        success = any(r.success for r in results)
        return SkillResult(content=combined, success=success, source=self.name)

    def _extract_symbols(self, text: str) -> list[str]:
        """Extract stock symbols from natural language query."""
        symbols = []

        # Check known aliases first
        text_lower = text.lower()
        for alias, symbol in STOCK_ALIASES.items():
            if alias.lower() in text_lower and symbol not in symbols:
                symbols.append(symbol)
                break  # One alias match is usually enough for single query

        if not symbols:
            # Look for explicit ticker symbols: 1-5 uppercase letters
            # or Taiwan format: 4 digits (.TW optional)
            # or crypto: BTC-USD format
            tickers = re.findall(r'\b([A-Z]{1,5}(?:-[A-Z]+)?)\b', text)
            tw_stocks = re.findall(r'\b(\d{4}(?:\.TW)?)\b', text)

            # Filter out common English words
            skip = {"I", "A", "AN", "IN", "OF", "OR", "AND", "THE", "TO", "AT",
                    "IT", "IS", "BE", "DO", "GO", "MY", "WE", "OK", "NO"}
            for t in tickers:
                if t not in skip and len(t) >= 2:
                    symbols.append(t)

            for s in tw_stocks:
                sym = s if s.endswith(".TW") else f"{s}.TW"
                if sym not in symbols:
                    symbols.append(sym)

        return symbols[:3]

    async def _fetch_quote(self, symbol: str) -> SkillResult:
        """Fetch stock quote from Yahoo Finance unofficial API."""
        import httpx

        # Normalize symbol
        symbol = symbol.upper()

        try:
            async with httpx.AsyncClient(
                timeout=12,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; NexusBot/1.0)",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                resp = await client.get(
                    f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
                    params={"interval": "1d", "range": "2d"},
                )
                resp.raise_for_status()
                data = resp.json()

            chart = data.get("chart", {})
            if chart.get("error"):
                err = chart["error"].get("description", "Unknown error")
                return SkillResult(
                    content=f"❌ 找不到「{symbol}」：{err}",
                    success=False, source=self.name,
                )

            result = chart.get("result", [])
            if not result:
                return SkillResult(
                    content=f"❌ 找不到「{symbol}」的行情資料。",
                    success=False, source=self.name,
                )

            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice", 0)
            prev_close = meta.get("previousClose") or meta.get("chartPreviousClose", 0)
            currency = meta.get("currency", "USD")
            name = meta.get("longName") or meta.get("shortName") or symbol
            market_state = meta.get("marketState", "")
            day_high = meta.get("regularMarketDayHigh", 0)
            day_low = meta.get("regularMarketDayLow", 0)
            volume = meta.get("regularMarketVolume", 0)

            # Calculate change
            change = price - prev_close if prev_close else 0
            change_pct = (change / prev_close * 100) if prev_close else 0

            if change > 0:
                arrow = _ARROW_UP
                change_str = f"+{change:.2f} (+{change_pct:.2f}%)"
            elif change < 0:
                arrow = _ARROW_DOWN
                change_str = f"{change:.2f} ({change_pct:.2f}%)"
            else:
                arrow = _FLAT
                change_str = "0.00 (0.00%)"

            # Format volume
            if volume >= 1_000_000:
                vol_str = f"{volume / 1_000_000:.1f}M"
            elif volume >= 1000:
                vol_str = f"{volume / 1000:.0f}K"
            else:
                vol_str = str(volume)

            state_zh = {"REGULAR": "交易中", "PRE": "盤前", "POST": "盤後", "CLOSED": "收盤"}.get(
                market_state, market_state
            )

            lines = [
                f"{arrow} **{name} ({symbol})**",
                f"💰 現價：**{price:.2f} {currency}**",
                f"📊 漲跌：{change_str}",
                f"📈 日高：{day_high:.2f} | 📉 日低：{day_low:.2f}",
            ]
            if volume:
                lines.append(f"📦 成交量：{vol_str}")
            if state_zh:
                lines.append(f"🕐 市場狀態：{state_zh}")

            return SkillResult(
                content="\n".join(lines),
                success=True, source=self.name,
                metadata={"symbol": symbol, "price": price, "currency": currency},
            )

        except httpx.TimeoutException:
            return SkillResult(
                content=f"⏱️ 查詢「{symbol}」超時，請稍後再試。",
                success=False, source=self.name,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return SkillResult(
                    content=f"❌ 找不到股票代碼「{symbol}」，請確認代碼。",
                    success=False, source=self.name,
                )
            return SkillResult(
                content=f"❌ 查詢失敗（HTTP {e.response.status_code}）",
                success=False, source=self.name,
            )
        except Exception as e:
            return SkillResult(
                content=f"❌ 股價查詢失敗：{e}",
                success=False, source=self.name,
            )
