"""Time-aware retrieval with decay functions for memory consolidation."""

from __future__ import annotations

import math
import time
from typing import Any


class TemporalDecay:
    """Implements various decay functions for memory relevance scoring."""

    @staticmethod
    def exponential_decay(timestamp: float, half_life_hours: float = 24.0) -> float:
        """Exponential decay: recent items are much more relevant.
        Returns 0.0-1.0 freshness score."""
        age_hours = (time.time() - timestamp) / 3600.0
        if age_hours < 0:
            return 1.0
        return math.exp(-0.693 * age_hours / half_life_hours)

    @staticmethod
    def power_decay(timestamp: float, exponent: float = 0.5) -> float:
        """Power law decay: slower forgetting than exponential."""
        age_hours = max(1.0, (time.time() - timestamp) / 3600.0)
        return 1.0 / (age_hours ** exponent)

    @staticmethod
    def step_decay(timestamp: float, thresholds: list[tuple[float, float]] | None = None) -> float:
        """Step function decay with configurable thresholds.
        Default: 1.0 for <1h, 0.8 for <24h, 0.5 for <7d, 0.2 for older."""
        if thresholds is None:
            thresholds = [
                (1.0, 1.0),      # < 1 hour
                (24.0, 0.8),     # < 1 day
                (168.0, 0.5),    # < 1 week
                (720.0, 0.2),    # < 1 month
            ]
        age_hours = (time.time() - timestamp) / 3600.0
        for threshold, score in thresholds:
            if age_hours < threshold:
                return score
        return 0.1


class TemporalRetriever:
    """Combines content relevance with temporal freshness."""

    def __init__(self, decay_type: str = "exponential", half_life_hours: float = 24.0) -> None:
        self.decay_type = decay_type
        self.half_life = half_life_hours
        self.decay = TemporalDecay()

    def score(self, content_score: float, timestamp: float, access_count: int = 0) -> float:
        """Combine content relevance with temporal decay and access frequency."""
        if self.decay_type == "exponential":
            freshness = self.decay.exponential_decay(timestamp, self.half_life)
        elif self.decay_type == "power":
            freshness = self.decay.power_decay(timestamp)
        else:
            freshness = self.decay.step_decay(timestamp)

        # Frequency bonus: accessed items stay relevant longer
        freq_bonus = min(0.3, access_count * 0.02)

        return content_score * 0.6 + freshness * 0.3 + freq_bonus * 0.1

    def rank_results(
        self, results: list[dict[str, Any]], score_key: str = "score", time_key: str = "timestamp"
    ) -> list[dict[str, Any]]:
        """Re-rank search results with temporal awareness."""
        for item in results:
            content_score = item.get(score_key, 0.5)
            timestamp = item.get(time_key, time.time())
            access_count = item.get("access_count", 0)
            item["temporal_score"] = self.score(content_score, timestamp, access_count)
        results.sort(key=lambda x: -x["temporal_score"])
        return results
