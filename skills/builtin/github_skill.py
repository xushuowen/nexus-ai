"""GitHub skill - search repos and view info using public API (no key needed)."""

from __future__ import annotations

import os
import re
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

async def _gh_headers(user_token: str | None = None) -> dict[str, str]:
    """Build GitHub API headers.

    Priority:
      1. Auth0 Token Vault (scoped per-user token) — if user is logged in via Auth0
      2. GITHUB_TOKEN env var (service-level token) — fallback for local / Telegram use
      3. No token — unauthenticated (60 req/hr limit)
    """
    headers = {"Accept": "application/vnd.github.v3+json"}

    # ── 1. Token Vault ──
    if user_token:
        try:
            from nexus.security.token_vault import get_connection_token
            vault_token = await get_connection_token(user_token, "github")
            if vault_token:
                headers["Authorization"] = f"Bearer {vault_token}"
                headers["X-Token-Source"] = "auth0-token-vault"
                return headers
        except Exception:
            pass  # fall through to env var

    # ── 2. Env var fallback ──
    env_token = os.getenv("GITHUB_TOKEN", "")
    if env_token:
        headers["Authorization"] = f"Bearer {env_token}"
        headers["X-Token-Source"] = "env-var"
    return headers

def _gh_rate_limit_msg(exc: Exception) -> str | None:
    """Return friendly rate-limit message if the error is a 403/429, else None."""
    msg = str(exc)
    if "403" in msg or "rate limit" in msg.lower() or "429" in msg:
        return (
            "⚠️ GitHub API 速率限制已達上限。\n"
            "已設定 GITHUB_TOKEN 可提高限制（5000次/小時），請稍後再試。"
        )
    return None


class GitHubSkill(BaseSkill):
    name = "github"
    description = "GitHub — 搜尋 repo、查看專案資訊（免費 API）"
    triggers = ["github", "repo", "開源", "star", "repository", "gh"]
    intent_patterns = [
        r"(幫我|請).{0,5}(找|搜|查).{0,10}(github|開源|repo|程式庫)",
        r"(github|開源|repo).{0,15}(有沒有|找找|搜尋|推薦|熱門)",
        r"(最多star|熱門|流行|trending).{0,10}(repo|開源|專案|程式庫)",
        r"(有什麼|哪些).{0,10}(好用|推薦|流行).{0,10}(開源|程式庫|框架|工具)",
        r"github.{0,5}(search|trending|搜尋|熱門)",
    ]
    category = "development"
    requires_llm = False

    instructions = (
        "GitHub 操作：\n"
        "1. 搜尋：「github search python web framework」\n"
        "2. 查看：「github info owner/repo」\n"
        "3. Trending：「github trending」"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()
        self._user_token = context.get("user_token")  # Auth0 JWT (may be None)

        if any(k in text for k in ["trending", "熱門", "流行"]):
            return await self._trending(query)
        elif any(k in text for k in ["info", "資訊", "details"]) or "/" in query:
            return await self._repo_info(query)
        else:
            return await self._search(query)

    async def _search(self, query: str) -> SkillResult:
        for t in self.triggers + ["search", "搜尋"]:
            query = query.replace(t, "").strip()
        query = query.strip()

        if not query:
            return SkillResult(content="請提供搜尋關鍵字，例如：「github search machine learning」", success=False, source=self.name)

        try:
            import httpx
            url = "https://api.github.com/search/repositories"
            params = {"q": query, "sort": "stars", "per_page": 5}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers=await _gh_headers(getattr(self, "_user_token", None)))
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if not items:
                return SkillResult(content=f"找不到「{query}」相關的 repo。", success=True, source=self.name)

            total = data.get("total_count", 0)
            lines = [f"🔍 GitHub 搜尋「{query}」（共 {total:,} 筆）\n"]
            for repo in items:
                stars = repo.get("stargazers_count", 0)
                lang = repo.get("language", "N/A")
                desc = (repo.get("description") or "")[:80]
                lines.append(f"**⭐ {stars:,} | {repo['full_name']}**")
                lines.append(f"   {desc}")
                lines.append(f"   📝 {lang} | 🔗 {repo['html_url']}")
                lines.append("")

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            rate_msg = _gh_rate_limit_msg(e)
            if rate_msg:
                return SkillResult(content=rate_msg, success=False, source=self.name)
            return SkillResult(content=f"GitHub 搜尋失敗: {e}", success=False, source=self.name)

    async def _repo_info(self, query: str) -> SkillResult:
        # Extract owner/repo pattern
        match = re.search(r'([\w.-]+/[\w.-]+)', query)
        if not match:
            return SkillResult(content="請提供 repo 名稱，格式：owner/repo", success=False, source=self.name)

        repo_name = match.group(1)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{repo_name}",
                    headers=await _gh_headers(getattr(self, "_user_token", None)),
                )
                resp.raise_for_status()
                repo = resp.json()

            lines = [
                f"📦 **{repo['full_name']}**\n",
                f"📝 {repo.get('description', 'No description')}",
                f"⭐ Stars: {repo.get('stargazers_count', 0):,}",
                f"🍴 Forks: {repo.get('forks_count', 0):,}",
                f"👀 Watchers: {repo.get('watchers_count', 0):,}",
                f"📝 Language: {repo.get('language', 'N/A')}",
                f"📅 Created: {repo.get('created_at', '')[:10]}",
                f"🔄 Updated: {repo.get('updated_at', '')[:10]}",
                f"📜 License: {repo.get('license', {}).get('name', 'None') if repo.get('license') else 'None'}",
                f"🔗 {repo['html_url']}",
            ]
            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            rate_msg = _gh_rate_limit_msg(e)
            if rate_msg:
                return SkillResult(content=rate_msg, success=False, source=self.name)
            return SkillResult(content=f"取得 repo 資訊失敗: {e}", success=False, source=self.name)

    async def _trending(self, query: str) -> SkillResult:
        """Get trending repos by searching recently created repos with most stars."""
        try:
            import httpx
            from datetime import datetime, timedelta
            since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            url = "https://api.github.com/search/repositories"
            params = {"q": f"created:>{since}", "sort": "stars", "per_page": 8}
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, params=params, headers=await _gh_headers(getattr(self, "_user_token", None)))
                resp.raise_for_status()
                data = resp.json()

            items = data.get("items", [])
            if not items:
                return SkillResult(content="無法取得 trending repos。", success=False, source=self.name)

            lines = ["🔥 **GitHub Trending（本週）**\n"]
            for i, repo in enumerate(items, 1):
                stars = repo.get("stargazers_count", 0)
                lang = repo.get("language", "")
                desc = (repo.get("description") or "")[:60]
                lines.append(f"**{i}. {repo['full_name']}** ⭐ {stars:,}")
                lines.append(f"   {desc}")
                if lang:
                    lines.append(f"   📝 {lang}")
                lines.append("")

            return SkillResult(content="\n".join(lines), success=True, source=self.name)

        except Exception as e:
            rate_msg = _gh_rate_limit_msg(e)
            if rate_msg:
                return SkillResult(content=rate_msg, success=False, source=self.name)
            return SkillResult(content=f"Trending 資料取得失敗：{e}", success=False, source=self.name)
