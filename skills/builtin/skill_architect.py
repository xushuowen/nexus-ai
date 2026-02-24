"""Skill Architect — runtime skill generation meta-skill.

Lets the AI create new skills at runtime by:
1. Understanding the user's request
2. Generating Python code for a new BaseSkill subclass
3. Basic security validation
4. Writing to skills/workspace/
5. Dynamically loading into the skill system
"""

from __future__ import annotations

import re
import importlib
from pathlib import Path
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult

# Forbidden patterns — covers direct imports, dynamic dispatch, and scope-escape tricks
FORBIDDEN_PATTERNS = [
    # Dangerous stdlib modules
    r"import\s+os\b", r"from\s+os\b", r"import\s+os\.path",
    r"import\s+subprocess", r"from\s+subprocess\b",
    r"import\s+shutil", r"from\s+shutil\b",
    r"import\s+socket", r"from\s+socket\b",
    r"import\s+ctypes", r"from\s+ctypes\b",
    r"import\s+signal", r"from\s+signal\b",
    r"import\s+pty", r"import\s+ptyprocess",
    # Dynamic code execution
    r"eval\s*\(", r"exec\s*\(", r"compile\s*\(",
    r"__import__\s*\(",
    # Dynamic attribute / scope introspection
    r"getattr\s*\(", r"setattr\s*\(", r"delattr\s*\(",
    r"globals\s*\(", r"locals\s*\(", r"vars\s*\(",
    r"__builtins__", r"__globals__", r"__class__",
    # Dynamic import
    r"importlib\b",
    # File-write operations
    r'open\s*\([^)]*["\'][wa+xb]+["\']',
    r"\.write\s*\(", r"rmtree", r"unlink\s*\(",
    r"\.remove\s*\(", r"os\.remove",
    # Shell / process spawn
    r"system\s*\(", r"popen\s*\(", r"Popen\s*\(",
    r"call\s*\(\[", r"check_output\s*\(",
]

SKILL_TEMPLATE = '''"""Auto-generated skill: {name}."""

from __future__ import annotations
from typing import Any
from nexus.skills.skill_base import BaseSkill, SkillResult


class {class_name}(BaseSkill):
    name = "{name}"
    description = """{description}"""
    triggers = {triggers}
    category = "workspace"
    requires_llm = {requires_llm}

    instructions = """{instructions}"""

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
{execute_body}
'''


class SkillArchitectSkill(BaseSkill):
    name = "skill_architect"
    description = "技能建築師 — 用 AI 自動建立新技能"
    triggers = ["建立技能", "create skill", "新技能", "new skill", "生成技能", "generate skill"]
    category = "meta"
    requires_llm = True

    instructions = (
        "技能建築師：用自然語言描述你想要的技能，AI 會自動生成。\n"
        "例如：「建立技能 匯率轉換」、「新技能 計算BMI」"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        llm = context.get("llm")
        if not llm:
            return SkillResult(
                content="需要 LLM 來生成技能。", success=False, source=self.name,
            )

        # Clean query
        for t in self.triggers:
            query = query.replace(t, "").strip()
        skill_description = query.strip(" ：:")

        if not skill_description or len(skill_description) < 3:
            return SkillResult(
                content="請描述你想要的技能，例如：「建立技能 匯率轉換 支援台幣美元日圓」",
                success=False, source=self.name,
            )

        # Generate skill code via LLM
        prompt = self._build_generation_prompt(skill_description)

        try:
            generated_code = await llm.complete(prompt, task_type="simple_tasks", source="skill_architect")
        except Exception as e:
            return SkillResult(
                content=f"技能生成失敗: {e}", success=False, source=self.name,
            )

        # Extract code block if wrapped in markdown
        code = self._extract_code(generated_code)

        # Security check
        violations = self._security_check(code)
        if violations:
            return SkillResult(
                content=f"⚠️ 生成的技能包含不安全的程式碼:\n" + "\n".join(f"- {v}" for v in violations),
                success=False, source=self.name,
            )

        # Extract skill name from code
        skill_name = self._extract_skill_name(code)
        if not skill_name:
            return SkillResult(
                content="無法從生成的程式碼中提取技能名稱。",
                success=False, source=self.name,
            )

        # Write to workspace
        workspace_dir = Path(__file__).parent.parent / "workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)

        skill_file = workspace_dir / f"{skill_name}.py"
        skill_file.write_text(code, encoding="utf-8")

        # Try to load dynamically
        skill_loader = context.get("skill_loader")
        load_result = ""
        if skill_loader:
            try:
                module_name = f"nexus.skills.workspace.{skill_name}"
                await skill_loader._load_module(module_name)
                load_result = "✅ 技能已自動載入！"
            except Exception as e:
                load_result = f"⚠️ 技能已儲存但載入失敗: {e}"
        else:
            load_result = "📁 技能已儲存，重啟後生效。"

        return SkillResult(
            content=(
                f"🏗️ **新技能已建立: `{skill_name}`**\n\n"
                f"📝 描述: {skill_description}\n"
                f"📁 路徑: `skills/workspace/{skill_name}.py`\n"
                f"{load_result}\n\n"
                f"```python\n{code[:1000]}\n```"
            ),
            success=True, source=self.name,
        )

    def _build_generation_prompt(self, description: str) -> str:
        return (
            "You are a Python skill generator for the Nexus AI system.\n"
            "Generate a complete Python skill class that inherits from BaseSkill.\n\n"
            "Requirements:\n"
            "- Class inherits from BaseSkill (from nexus.skills.skill_base import BaseSkill, SkillResult)\n"
            "- Has name, description, triggers, category, requires_llm attributes\n"
            "- Implements async execute(self, query, context) -> SkillResult\n"
            "- Keep it simple and functional\n"
            "- Use only safe imports (httpx, json, re, math, datetime, etc.)\n"
            "- DO NOT use os, subprocess, shutil, eval, exec\n"
            "- Return SkillResult(content=..., success=True/False, source=self.name)\n"
            "- Description and user messages should be in Traditional Chinese (繁體中文)\n\n"
            f"Skill to create: {description}\n\n"
            "Generate ONLY the Python code, no explanation:\n"
        )

    def _extract_code(self, text: str) -> str:
        """Extract Python code from markdown code blocks."""
        match = re.search(r"```python\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*\n(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

    def _security_check(self, code: str) -> list[str]:
        """Check for forbidden patterns."""
        violations = []
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, code):
                violations.append(f"不允許的模式：{pattern}")
        return violations

    def _extract_skill_name(self, code: str) -> str | None:
        """Extract skill name from generated code."""
        match = re.search(r'name\s*=\s*["\'](\w+)["\']', code)
        if match:
            return match.group(1)
        return None
