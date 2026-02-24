"""News aggregation skill using RSS feeds (free, no API key)."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


# Category → RSS feed URLs
RSS_FEEDS = {
    "科技": [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ],
    "世界": [
        ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters", "https://www.reutersagency.com/feed/"),
    ],
    "健康": [
        ("Medical News Today", "https://www.medicalnewstoday.com/newsfeeds/rss"),
        ("WHO News", "https://www.who.int/rss-feeds/news-english.xml"),
    ],
    "台灣": [
        ("中央社", "https://feeds.feedburner.com/rsscna/politics"),
    ],
}

CATEGORY_ALIASES = {
    "tech": "科技", "technology": "科技", "科技": "科技",
    "world": "世界", "國際": "世界", "世界": "世界",
    "health": "健康", "醫療": "健康", "健康": "健康",
    "taiwan": "台灣", "tw": "台灣", "台灣": "台灣",
}


class NewsSkill(BaseSkill):
    name = "news"
    description = "新聞聚合 — 從 RSS 源取得最新新聞（科技、世界、健康、台灣）"
    triggers = ["新聞", "news", "頭條", "headline", "最新消息", "headlines"]
    intent_patterns = [
        r"(最近|這週|最新).{0,10}(發生|消息|大事|時事|動態)",
        r"有什麼.{0,10}(大事|新鮮事|值得關注|新聞|重要)",
        r"(世界|台灣|國際|科技|健康|醫療).{0,5}(最新|發生了什麼|新聞|動態)",
        r"幫我(看|找|查).{0,5}(新聞|消息|時事|頭條)",
        r"(今天|最近).{0,5}(有什麼|什麼).{0,5}(新聞|大事|消息|頭條)",
        r"(關心|了解|知道).{0,10}(最新|今日|近期).{0,5}(動態|消息|時事)",
    ]
    category = "information"
    requires_llm = False

    instructions = (
        "新聞聚合（RSS）：\n"
        "1. 所有新聞：「新聞」\n"
        "2. 分類：「新聞 科技」「news health」\n"
        "3. 支援分類：科技、世界、健康、台灣"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Detect category
        category = self._detect_category(query)
        feeds = RSS_FEEDS.get(category, []) if category else []

        if not feeds:
            # Fetch from all categories
            all_feeds = []
            for cat_feeds in RSS_FEEDS.values():
                all_feeds.extend(cat_feeds)
            feeds = all_feeds
            category = "所有"

        try:
            articles = await self._fetch_feeds(feeds)
            if not articles:
                return SkillResult(content=f"無法取得{category}新聞。", success=False, source=self.name)

            lines = [f"📰 **{category}新聞**（{len(articles)} 則）\n"]
            for i, (source, title, link, pub_date) in enumerate(articles[:8], 1):
                lines.append(f"**{i}. {title}**")
                lines.append(f"   📌 {source}" + (f" · {pub_date}" if pub_date else ""))
                if link:
                    lines.append(f"   🔗 {link}")
                lines.append("")

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"新聞取得失敗: {e}", success=False, source=self.name)

    def _detect_category(self, query: str) -> str | None:
        text = query.lower()
        for alias, cat in CATEGORY_ALIASES.items():
            if alias in text:
                return cat
        return None

    async def _fetch_feeds(self, feeds: list[tuple[str, str]]) -> list[tuple[str, str, str, str]]:
        """Fetch and parse RSS feeds. Returns [(source, title, link, date)]."""
        articles = []

        try:
            import feedparser
        except ImportError:
            # Fallback to httpx + basic XML parsing
            return await self._fetch_feeds_basic(feeds)

        import httpx
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for source_name, url in feeds:
                try:
                    resp = await client.get(url, headers={"User-Agent": "Nexus-AI/1.0"})
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:5]:
                        title = entry.get("title", "").strip()
                        link = entry.get("link", "")
                        pub = entry.get("published", "")[:16] if entry.get("published") else ""
                        if title:
                            articles.append((source_name, title, link, pub))
                except Exception:
                    continue

        return articles

    async def _fetch_feeds_basic(self, feeds: list[tuple[str, str]]) -> list[tuple[str, str, str, str]]:
        """Basic XML RSS parsing without feedparser."""
        articles = []
        import httpx

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for source_name, url in feeds:
                try:
                    resp = await client.get(url, headers={"User-Agent": "Nexus-AI/1.0"})
                    text = resp.text
                    titles = re.findall(r'<title[^>]*>(.*?)</title>', text, re.DOTALL)
                    links = re.findall(r'<link[^>]*>(.*?)</link>', text, re.DOTALL)
                    for i, title in enumerate(titles[1:6]):  # skip feed title
                        title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title).strip()
                        title = re.sub(r'<[^>]+>', '', title)
                        link = links[i + 1].strip() if i + 1 < len(links) else ""
                        if title:
                            articles.append((source_name, title, link, ""))
                except Exception:
                    continue

        return articles
