"""Per-user rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict

from nexus import config


class RateLimiter:
    """Simple sliding window rate limiter."""

    def __init__(self) -> None:
        self.max_per_minute = config.get("security.rate_limit_per_minute", 30)
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, user_id: str) -> tuple[bool, int]:
        """Check if user can make a request. Returns (allowed, remaining)."""
        now = time.time()
        window_start = now - 60.0

        # Clean old entries
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]

        count = len(self._requests[user_id])
        remaining = max(0, self.max_per_minute - count)

        if count >= self.max_per_minute:
            return False, 0

        self._requests[user_id].append(now)
        return True, remaining - 1

    def get_usage(self, user_id: str) -> dict[str, int]:
        now = time.time()
        window_start = now - 60.0
        self._requests[user_id] = [
            t for t in self._requests[user_id] if t > window_start
        ]
        count = len(self._requests[user_id])
        return {
            "requests_in_window": count,
            "max_per_minute": self.max_per_minute,
            "remaining": max(0, self.max_per_minute - count),
        }
