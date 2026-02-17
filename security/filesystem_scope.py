"""Allowlist-based file access control."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus import config


class FilesystemScope:
    """Controls which paths the system can read/write to."""

    def __init__(self) -> None:
        self._allowed_paths: list[Path] = []
        raw = config.get("security.allowed_paths", ["./data", "./workspace"])
        for p in raw:
            resolved = Path(p).resolve()
            resolved.mkdir(parents=True, exist_ok=True)
            self._allowed_paths.append(resolved)

    def is_allowed(self, path: str | Path) -> bool:
        """Check if a path is within allowed scope."""
        target = Path(path).resolve()
        return any(
            target == allowed or target.is_relative_to(allowed)
            for allowed in self._allowed_paths
        )

    def check_read(self, path: str | Path) -> tuple[bool, str]:
        if not self.is_allowed(path):
            return False, f"Path {path} is outside allowed scope"
        if not Path(path).exists():
            return False, f"Path {path} does not exist"
        return True, ""

    def check_write(self, path: str | Path) -> tuple[bool, str]:
        if not self.is_allowed(path):
            return False, f"Path {path} is outside allowed scope"
        parent = Path(path).parent
        if not parent.exists():
            return False, f"Parent directory {parent} does not exist"
        return True, ""

    def get_allowed_paths(self) -> list[str]:
        return [str(p) for p in self._allowed_paths]
