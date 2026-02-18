"""Autonomous coding agent (OpenClaw-style) — code generation, debug, and execution."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent
from nexus import config

CODER_SYSTEM = """You are an expert autonomous coding agent. You can:
1. Generate clean, efficient, well-documented code
2. Debug and fix errors when given error messages
3. Explain code step by step
4. Refactor and optimize existing code

Rules:
- Follow best practices for the requested language
- Include error handling where appropriate
- When debugging, identify the root cause and provide the fix
- Always wrap code in markdown code blocks with language tag
- Respond in the same language as the user (Chinese → Chinese, etc.)"""


class CoderAgent(BaseAgent):
    name = "coder"
    description = "Autonomous code generation, debugging, and execution"
    capabilities = [AgentCapability.CODE]
    priority = 8

    def __init__(self) -> None:
        super().__init__()
        self._llm = None

    def set_llm(self, llm) -> None:
        self._llm = llm

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = [
            "code", "function", "class", "implement", "debug", "fix", "error",
            "python", "javascript", "typescript", "rust", "java", "html", "css",
            "write a", "create a", "program", "script", "api", "algorithm",
            "bug", "syntax", "compile", "refactor", "寫程式", "程式碼", "debug",
        ]
        score = sum(0.15 for kw in keywords if kw in text)
        if "```" in message.content:
            score += 0.3
        return min(1.0, score)

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        if not self._llm:
            return AgentResult(content="Coder agent not connected to LLM.", confidence=0.0, source_agent=self.name)

        # Detect mode: generate, debug, or explain
        mode = self._detect_mode(message.content)
        memory_ctx = context.get("memory", "")
        history_ctx = context.get("history", "")

        # Build prompt with context
        parts = []
        if history_ctx:
            parts.append(f"Recent conversation:\n{history_ctx}")
        if memory_ctx:
            parts.append(f"Relevant context:\n{memory_ctx}")
        parts.append(f"User request:\n{message.content}")

        prompt = "\n\n".join(parts)

        if mode == "debug":
            prompt += "\n\nAnalyze the error, identify the root cause, and provide the corrected code."
        elif mode == "explain":
            prompt += "\n\nExplain the code step by step, clearly and concisely."

        response = await self._llm.complete(
            prompt, task_type="code_generation", source="coder_agent",
            system_prompt=CODER_SYSTEM,
        )

        # Try to execute Python code if it's a simple snippet
        code_blocks = self._extract_python_code(response)
        execution_result = ""
        if code_blocks and mode == "generate" and self._is_safe_to_run(code_blocks[0]):
            execution_result = await self._safe_execute_python(code_blocks[0])
            if execution_result:
                response += f"\n\n**執行結果:**\n```\n{execution_result}\n```"

        has_code = "```" in response or "def " in response or "function " in response
        confidence = 0.85 if has_code else 0.6

        return AgentResult(
            content=response,
            confidence=confidence,
            source_agent=self.name,
            reasoning_trace=[f"Mode: {mode}", "Generated code solution"],
        )

    def _detect_mode(self, text: str) -> str:
        text_lower = text.lower()
        debug_kw = ["debug", "error", "fix", "bug", "traceback", "exception", "修復", "錯誤"]
        explain_kw = ["explain", "how does", "what does", "解釋", "說明", "怎麼運作"]

        if any(kw in text_lower for kw in debug_kw):
            return "debug"
        if any(kw in text_lower for kw in explain_kw):
            return "explain"
        return "generate"

    def _extract_python_code(self, text: str) -> list[str]:
        """Extract Python code blocks from markdown."""
        blocks = re.findall(r'```(?:python)?\n(.*?)```', text, re.DOTALL)
        return [b.strip() for b in blocks if b.strip()]

    def _is_safe_to_run(self, code: str) -> bool:
        """Basic safety check for auto-execution."""
        dangerous = [
            "import os", "import sys", "import subprocess", "import shutil",
            "open(", "exec(", "eval(", "__import__", "globals(", "locals(",
            "rm ", "del ", "rmdir", "unlink",
        ]
        code_lower = code.lower()
        if any(d in code_lower for d in dangerous):
            return False
        # Only run short snippets
        if len(code.splitlines()) > 30:
            return False
        return True

    async def _safe_execute_python(self, code: str, timeout: int = 5) -> str:
        """Execute Python code in a sandboxed subprocess."""
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
                f.write(code)
                tmp_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "python", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(config.data_dir()),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace").strip()
            if stderr:
                err = stderr.decode(errors="replace").strip()
                if err:
                    output += f"\n[stderr] {err}"

            # Cleanup
            try:
                Path(tmp_path).unlink()
            except Exception:
                pass

            return output[:2000] if output else ""
        except asyncio.TimeoutError:
            return "(execution timed out)"
        except Exception as e:
            return f"(execution error: {e})"
