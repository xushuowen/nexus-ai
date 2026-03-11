"""Model routing configuration - decides which model to use for each task type."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from nexus import config


@dataclass
class ModelSpec:
    model_id: str
    max_tokens: int
    temperature: float
    use_for: list[str]
    api_base: str = ""
    extra_config: dict = None  # 本地模型專用設定（model_path, mmproj_path, n_threads）

    def __post_init__(self):
        if self.extra_config is None:
            self.extra_config = {}


class ModelRouter:
    """Routes tasks to appropriate models based on complexity and type."""

    def __init__(self) -> None:
        cfg = config.load_config()["providers"]
        self.primary_name: str = cfg["primary"]
        self.local_primary_name: str = cfg.get("local_primary", "")
        self.fallback_name: str = cfg["fallback"]
        # NEXUS_BRAIN_MODE env var overrides config.yaml (useful for Cloud Run)
        self.brain_mode: str = os.environ.get("NEXUS_BRAIN_MODE") or cfg.get("brain_mode", "auto")
        self._models: dict[str, ModelSpec] = {}
        for name, mcfg in cfg.get("models", {}).items():
            self._models[name] = ModelSpec(
                model_id=mcfg["model_id"],
                max_tokens=mcfg["max_tokens"],
                temperature=mcfg["temperature"],
                use_for=mcfg.get("use_for", []),
                api_base=mcfg.get("api_base", ""),
                extra_config={
                    k: v for k, v in mcfg.items()
                    if k not in {"model_id", "max_tokens", "temperature", "use_for", "api_base"}
                },
            )

    def route(self, task_type: str = "general") -> ModelSpec:
        """Select the best model for a task type."""
        # Check if any model explicitly handles this task type
        for name, spec in self._models.items():
            if task_type in spec.use_for:
                return spec
        # Default to primary (Flash for speed/cost)
        return self._models.get(self.primary_name, self._get_fallback())

    def get_primary(self) -> ModelSpec:
        return self._models.get(self.primary_name, self._get_fallback())

    def get_fallback(self) -> ModelSpec:
        return self._models.get(self.fallback_name, self.get_primary())

    def _get_fallback(self) -> ModelSpec:
        """Last resort fallback."""
        return ModelSpec(
            model_id="gemini/gemini-2.0-flash",
            max_tokens=2000,
            temperature=0.7,
            use_for=["general"],
        )

    def get_for_complexity(self, complexity: str) -> ModelSpec:
        """Route by complexity: 'simple', 'moderate', 'complex'."""
        mapping = {
            "simple": self.primary_name,      # Flash
            "moderate": self.primary_name,     # Flash still
            "complex": self.fallback_name,     # Pro
        }
        name = mapping.get(complexity, self.primary_name)
        return self._models.get(name, self._get_fallback())
