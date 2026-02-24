"""Token Budget Controller - the critical safety valve for free API tiers."""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from nexus import config


class BudgetExhausted(Exception):
    """Raised when the daily token budget is exhausted."""


class BudgetController:
    """Tracks and enforces daily token budgets across all LLM calls."""

    def __init__(self) -> None:
        cfg = config.load_config()["budget"]
        self.daily_limit: int = cfg["daily_limit_tokens"]
        self.per_request_max: int = cfg["per_request_max_tokens"]
        self.curiosity_daily_ops: int = cfg["curiosity_daily_ops"]
        self.curiosity_per_op_tokens: int = cfg["curiosity_per_op_tokens"]
        self.warning_threshold: float = cfg["warning_threshold"]
        self.hard_stop: bool = cfg["hard_stop"]
        self.reset_hour: int = cfg["reset_hour"]

        self._tokens_used: int = 0
        self._curiosity_ops_used: int = 0
        self._request_count: int = 0
        self._last_reset: datetime = datetime.now()
        self._history: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._state_path = config.data_dir() / "budget_state.json"
        self._load_state()

    def _load_state(self) -> None:
        if self._state_path.exists():
            try:
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                last_reset = datetime.fromisoformat(data.get("last_reset", ""))
                if self._should_reset(last_reset):
                    self._reset()
                else:
                    self._tokens_used = data.get("tokens_used", 0)
                    self._curiosity_ops_used = data.get("curiosity_ops_used", 0)
                    self._request_count = data.get("request_count", 0)
                    self._last_reset = last_reset
            except (json.JSONDecodeError, ValueError):
                self._reset()

    def _save_state(self) -> None:
        data = {
            "tokens_used": self._tokens_used,
            "curiosity_ops_used": self._curiosity_ops_used,
            "request_count": self._request_count,
            "last_reset": self._last_reset.isoformat(),
        }
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: write to .tmp then rename so a crash mid-write
        # never leaves a corrupt state file.
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(self._state_path)

    def _should_reset(self, since: datetime) -> bool:
        now = datetime.now()
        reset_today = now.replace(hour=self.reset_hour, minute=0, second=0, microsecond=0)
        if now >= reset_today and since < reset_today:
            return True
        if now < reset_today:
            reset_yesterday = reset_today - timedelta(days=1)
            if since < reset_yesterday:
                return True
        return False

    def _reset(self) -> None:
        self._tokens_used = 0
        self._curiosity_ops_used = 0
        self._request_count = 0
        self._last_reset = datetime.now()
        self._history.clear()

    async def check_and_maybe_reset(self) -> None:
        async with self._lock:
            if self._should_reset(self._last_reset):
                self._reset()
                self._save_state()

    async def request_tokens(self, estimated_tokens: int, source: str = "user") -> bool:
        """Request permission to use tokens. Returns True if allowed."""
        await self.check_and_maybe_reset()
        async with self._lock:
            if self.hard_stop and self._tokens_used + estimated_tokens > self.daily_limit:
                return False
            return True

    async def consume_tokens(self, tokens: int, source: str = "user", metadata: dict | None = None) -> None:
        """Record actual token consumption after an LLM call."""
        async with self._lock:
            self._tokens_used += tokens
            self._request_count += 1
            self._history.append({
                "time": datetime.now().isoformat(),
                "tokens": tokens,
                "source": source,
                "metadata": metadata or {},
            })
            # Cap history to avoid unbounded memory growth
            if len(self._history) > 500:
                self._history = self._history[-500:]
            self._save_state()

    async def request_curiosity_op(self, estimated_tokens: int) -> bool:
        """Request permission for a curiosity engine operation."""
        await self.check_and_maybe_reset()
        async with self._lock:
            if self._curiosity_ops_used >= self.curiosity_daily_ops:
                return False
            if estimated_tokens > self.curiosity_per_op_tokens:
                return False
            if self.hard_stop and self._tokens_used + estimated_tokens > self.daily_limit:
                return False
            self._curiosity_ops_used += 1
            self._save_state()
            return True

    @property
    def tokens_used(self) -> int:
        return self._tokens_used

    @property
    def tokens_remaining(self) -> int:
        return max(0, self.daily_limit - self._tokens_used)

    @property
    def usage_ratio(self) -> float:
        if self.daily_limit == 0:
            return 1.0
        return self._tokens_used / self.daily_limit

    @property
    def is_warning(self) -> bool:
        return self.usage_ratio >= self.warning_threshold

    @property
    def is_exhausted(self) -> bool:
        return self.hard_stop and self._tokens_used >= self.daily_limit

    @property
    def curiosity_ops_remaining(self) -> int:
        return max(0, self.curiosity_daily_ops - self._curiosity_ops_used)

    def get_status(self) -> dict[str, Any]:
        return {
            "tokens_used": self._tokens_used,
            "tokens_remaining": self.tokens_remaining,
            "daily_limit": self.daily_limit,
            "usage_ratio": round(self.usage_ratio, 4),
            "is_warning": self.is_warning,
            "is_exhausted": self.is_exhausted,
            "request_count": self._request_count,
            "curiosity_ops_used": self._curiosity_ops_used,
            "curiosity_ops_remaining": self.curiosity_ops_remaining,
        }
