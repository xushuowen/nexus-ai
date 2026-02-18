"""Skill loader with auto-discovery and Level 1 index management."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

logger = logging.getLogger(__name__)


class SkillLoader:
    """Discovers, loads, and manages skills with three-layer architecture."""

    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}
        self._index: list[dict[str, str]] = []  # Level 1 cache

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill
        self._rebuild_index()
        logger.info(f"Registered skill: {skill.name}")

    def _rebuild_index(self) -> None:
        """Rebuild the Level 1 index cache."""
        self._index = [s.get_index() for s in self._skills.values()]

    def get_index(self) -> list[dict[str, str]]:
        """Get Level 1 index (name + description + triggers) for all skills."""
        return self._index

    def get_index_text(self) -> str:
        """Get human-readable index for LLM context."""
        lines = []
        for entry in self._index:
            lines.append(f"- {entry['name']}: {entry['description']} [triggers: {entry['triggers']}]")
        return "\n".join(lines)

    def match(self, text: str) -> BaseSkill | None:
        """Find the best matching skill for input text (Level 1 matching)."""
        best_skill = None
        best_score = 0
        for skill in self._skills.values():
            score = skill.match_score(text)
            if score > best_score:
                best_score = score
                best_skill = skill
        # Require at least 1 trigger match
        if best_score >= 1:
            return best_skill
        return None

    async def execute(self, skill: BaseSkill, query: str, context: dict[str, Any]) -> SkillResult:
        """Execute a skill (Level 3)."""
        try:
            return await skill.execute(query, context)
        except Exception as e:
            logger.error(f"Skill '{skill.name}' failed: {e}", exc_info=True)
            return SkillResult(content=f"Skill error: {e}", success=False, source=skill.name)

    def list_skills(self) -> list[BaseSkill]:
        return list(self._skills.values())

    def get(self, name: str) -> BaseSkill | None:
        return self._skills.get(name)

    async def auto_discover(self) -> None:
        """Auto-discover builtin and workspace skills."""
        # Builtin skills
        builtin_dir = Path(__file__).parent / "builtin"
        await self._load_from_dir(builtin_dir, "nexus.skills.builtin")

        # Workspace skills (user-defined)
        workspace_dir = Path(__file__).parent / "workspace"
        if workspace_dir.exists():
            for skill_dir in workspace_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "__init__.py").exists():
                    module_name = f"nexus.skills.workspace.{skill_dir.name}"
                    await self._load_module(module_name)

    async def _load_from_dir(self, directory: Path, package: str) -> None:
        if not directory.exists():
            return
        for py_file in directory.glob("*.py"):
            if py_file.name.startswith("_"):
                continue
            module_name = f"{package}.{py_file.stem}"
            await self._load_module(module_name)

    async def _load_module(self, module_name: str) -> None:
        try:
            mod = importlib.import_module(module_name)
            for attr_name in dir(mod):
                attr = getattr(mod, attr_name)
                if (isinstance(attr, type) and issubclass(attr, BaseSkill)
                        and attr is not BaseSkill):
                    skill = attr()
                    await skill.initialize()
                    self.register(skill)
        except Exception as e:
            logger.warning(f"Failed to load skill from {module_name}: {e}")

    async def shutdown_all(self) -> None:
        for skill in self._skills.values():
            try:
                await skill.shutdown()
            except Exception:
                pass
        self._skills.clear()
