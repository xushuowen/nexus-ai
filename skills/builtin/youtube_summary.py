"""YouTube summary skill - extract info and summarize videos."""

from __future__ import annotations

import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult


class YouTubeSummarySkill(BaseSkill):
    name = "youtube_summary"
    description = "YouTube 影片摘要 — 提取影片資訊並用 AI 生成摘要"
    triggers = ["youtube", "youtu.be", "影片摘要", "yt", "視頻", "影片"]
    intent_patterns = [
        r"https?://(www\.)?(youtube\.com|youtu\.be)/\S+",
        r"(幫我|請).{0,5}(看|分析|摘要|總結|整理).{0,10}(影片|視頻|youtube)",
        r"(這支|這個|這部).{0,5}(影片|視頻).{0,10}(說|講|在說|的重點)",
        r"(youtube|影片).{0,10}(重點|摘要|總結|幫我看)",
    ]
    category = "media"
    requires_llm = True

    instructions = "提供 YouTube 連結或搜尋關鍵字，自動提取影片資訊並生成摘要。"

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Extract YouTube URL
        url_match = re.search(
            r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+))',
            query,
        )

        if not url_match:
            return SkillResult(
                content="請提供 YouTube 影片連結，例如：https://youtube.com/watch?v=xxx",
                success=False, source=self.name,
            )

        video_url = url_match.group(1)
        video_id = url_match.group(2)

        # Try to get transcript
        transcript_text = await self._get_transcript(video_id)

        # Get video info from page
        video_info = await self._get_video_info(video_url)

        llm = context.get("llm")
        if not llm:
            # No LLM, just return raw info
            lines = [f"🎬 **YouTube 影片資訊**\n"]
            if video_info.get("title"):
                lines.append(f"📌 標題: {video_info['title']}")
            if video_info.get("description"):
                lines.append(f"\n📝 描述:\n{video_info['description'][:500]}")
            if transcript_text:
                lines.append(f"\n📜 字幕（前 500 字）:\n{transcript_text[:500]}")
            lines.append(f"\n🔗 {video_url}")
            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        # Build prompt for LLM summary
        content_parts = []
        if video_info.get("title"):
            content_parts.append(f"Title: {video_info['title']}")
        if video_info.get("description"):
            content_parts.append(f"Description: {video_info['description'][:1000]}")
        if transcript_text:
            content_parts.append(f"Transcript: {transcript_text[:2000]}")

        if not content_parts:
            return SkillResult(content="無法提取影片資訊。", success=False, source=self.name)

        prompt = (
            "請用繁體中文摘要以下 YouTube 影片，列出 3-5 個重點：\n\n"
            + "\n\n".join(content_parts)
        )

        try:
            summary = await llm.complete(prompt, task_type="simple_tasks", source="youtube_summary")
            result = f"🎬 **影片摘要**\n"
            if video_info.get("title"):
                result += f"📌 {video_info['title']}\n\n"
            result += summary
            result += f"\n\n🔗 {video_url}"
            return SkillResult(content=result, success=True, source=self.name)
        except Exception as e:
            return SkillResult(content=f"摘要生成失敗: {e}", success=False, source=self.name)

    async def _get_transcript(self, video_id: str) -> str:
        """Try to get YouTube transcript."""
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["zh-TW", "zh", "en"])
            return " ".join(entry["text"] for entry in transcript)
        except Exception:
            return ""

    async def _get_video_info(self, url: str) -> dict[str, str]:
        """Extract basic video info from YouTube page."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                html = resp.text

            info = {}
            # Extract title
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                title = title_match.group(1).replace(" - YouTube", "").strip()
                info["title"] = title

            # Extract description from meta
            desc_match = re.search(r'<meta name="description" content="(.*?)"', html)
            if desc_match:
                info["description"] = desc_match.group(1)

            return info
        except Exception:
            return {}
