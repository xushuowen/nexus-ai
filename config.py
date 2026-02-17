"""Configuration loader for Nexus AI."""

import os
from pathlib import Path
from typing import Any

import yaml

_BASE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _BASE_DIR / "config.yaml"
_config_cache: dict | None = None


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
    if os.getenv("TELEGRAM_BOT_TOKEN"):
        cfg.setdefault("gateway", {}).setdefault("telegram", {})["token"] = os.getenv("TELEGRAM_BOT_TOKEN")
    if os.getenv("NEXUS_DAILY_LIMIT"):
        cfg["budget"]["daily_limit_tokens"] = int(os.getenv("NEXUS_DAILY_LIMIT"))
    if path is None:
        _config_cache = cfg
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
