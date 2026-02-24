"""Web browsing and scraping specialist agent."""

from __future__ import annotations

from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent


class WebAgent(BaseAgent):
    name = "web"
    description = "Web browsing, URL fetching, and content extraction"
    capabilities = [AgentCapability.WEB]
    priority = 5

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["url", "website", "browse", "fetch", "scrape", "http",
                     "www", "webpage", "download"]
        score = sum(0.2 for kw in keywords if kw in text)
        if "http" in text:
            score += 0.3
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        import re
        urls = re.findall(r'https?://\S+', message.content)

        if urls:
            results = []
            for url in urls[:3]:
                try:
                    content = await self._fetch_url(url)
                    results.append(f"Content from {url}:\n{content[:1000]}")
                except Exception as e:
                    results.append(f"Failed to fetch {url}: {e}")
            return AgentResult(
                content="\n\n".join(results), confidence=0.8, source_agent=self.name,
            )
        else:
            return AgentResult(
                content="Please provide a URL to fetch, or use the research agent for general web searches.",
                confidence=0.3, source_agent=self.name,
            )

    async def _fetch_url(self, url: str) -> str:
        """Fetch URL content using httpx (with SSRF protection)."""
        from nexus.security.url_filter import is_url_safe
        safe, reason = is_url_safe(url)
        if not safe:
            return f"URL blocked: {reason}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                # Reject responses that are too large (> 5 MB) to avoid memory exhaustion
                content_length = int(resp.headers.get("content-length", 0))
                if content_length > 5_000_000:
                    return f"Content too large ({content_length // 1024:,} KB). Only pages under 5 MB are supported."
                # Simple HTML to text
                text = resp.text
                import re
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:3000]
        except ImportError:
            return "httpx not installed. Install with: pip install httpx"
        except Exception as e:
            return f"Error fetching URL: {e}"
