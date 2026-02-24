"""Configuration loader for Nexus AI."""

import logging
import os
from pathlib import Path
from typing import Any

import yaml

_BASE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _BASE_DIR / "config.yaml"
_config_cache: dict | None = None
logger = logging.getLogger(__name__)

# Keys that must exist and have non-zero/non-empty values.
# Format: (dot_key, friendly_label, type_check)
_REQUIRED_KEYS: list[tuple[str, str, type]] = [
    ("app.port", "app.port", int),
    ("budget.daily_limit_tokens", "budget.daily_limit_tokens", int),
    ("memory.sqlite_path", "memory.sqlite_path", str),
]


def validate(cfg: dict) -> None:
    """Emit startup warnings for missing or invalid config keys."""
    for dot_key, label, expected_type in _REQUIRED_KEYS:
        keys = dot_key.split(".")
        val: Any = cfg
        for k in keys:
            val = val.get(k) if isinstance(val, dict) else None
        if val is None:
            logger.warning("Config: '%s' is missing — using default", label)
        elif not isinstance(val, expected_type):
            logger.warning(
                "Config: '%s' expected %s but got %s",
                label, expected_type.__name__, type(val).__name__,
            )
        elif expected_type is int and val <= 0:
            logger.warning("Config: '%s' should be > 0 (got %d)", label, val)

    # Check at least one LLM provider key is available
    providers = {
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY",
        "GROQ_API_KEY", "GITHUB_TOKEN",
    }
    if not any(os.getenv(k) for k in providers):
        logger.warning(
            "Config: no LLM provider API key found in environment — "
            "set at least one of: %s", ", ".join(sorted(providers))
        )


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache YAML configuration."""
    global _config_cache
    if _config_cache is not None and path is None:
        return _config_cache
    p = path or _CONFIG_PATH
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Override with environment variables
    if os.getenv("GEMINI_API_KEY"):
        cfg.setdefault("api_keys", {})["gemini"] = os.getenv("GEMINI_API_KEY")
    if os.getenv("GROQ_API_KEY"):
        cfg.setdefault("api_keys", {})["groq"] = os.getenv("GROQ_API_KEY")
    if os.getenv("OPENAI_API_KEY"):
        cfg.setdefault("api_keys", {})["openai"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("GITHUB_TOKEN"):
        cfg.setdefault("api_keys", {})["github"] = os.getenv("GITHUB_TOKEN")
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        cfg.setdefault("gateway", {}).setdefault("telegram", {})["token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("NEXUS_DAILY_LIMIT"):
        cfg["budget"]["daily_limit_tokens"] = int(os.getenv("NEXUS_DAILY_LIMIT"))
    if path is None:
        _config_cache = cfg
        validate(cfg)
    return cfg


def get(key: str, default: Any = None) -> Any:
    """Get a nested config value using dot notation: 'budget.daily_limit_tokens'."""
    cfg = load_config()
    keys = key.split(".")
    val = cfg
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return default
        if val is None:
            return default
    return val


def base_dir() -> Path:
    return _BASE_DIR


def data_dir() -> Path:
    d = _BASE_DIR / "data"
    d.mkdir(exist_ok=True)
    return d
