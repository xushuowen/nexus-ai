"""File operations specialist agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nexus.core.agent_base import AgentCapability, AgentMessage, AgentResult, BaseAgent


class FileAgent(BaseAgent):
    name = "file"
    description = "File reading, writing, searching, and management"
    capabilities = [AgentCapability.FILE]
    priority = 5

    def __init__(self) -> None:
        super().__init__()
        self._allowed_paths: list[str] = ["./data", "./workspace"]

    async def initialize(self) -> None:
        await super().initialize()
        from nexus import config
        self._allowed_paths = config.get("security.allowed_paths", ["./data", "./workspace"])
        for p in self._allowed_paths:
            Path(p).mkdir(parents=True, exist_ok=True)

    def can_handle(self, message: AgentMessage, context: dict[str, Any]) -> float:
        text = message.content.lower()
        keywords = ["file", "read", "write", "save", "create", "delete",
                     "folder", "directory", "list files", "open"]
        return min(1.0, sum(0.2 for kw in keywords if kw in text))

    def _is_allowed(self, path: str) -> bool:
        abs_path = str(Path(path).resolve())
        for allowed in self._allowed_paths:
            if abs_path.startswith(str(Path(allowed).resolve())):
                return True
        return False

    async def process(self, message: AgentMessage, context: dict[str, Any]) -> AgentResult:
        text = message.content.lower()

        if "list" in text or "show" in text:
            return await self._list_files()
        elif "read" in text:
            return await self._read_file(message.content)
        elif "write" in text or "save" in text or "create" in text:
            return await self._write_file(message.content)
        else:
            return AgentResult(
                content="I can help with file operations: list, read, write, or create files in the workspace.",
                confidence=0.5, source_agent=self.name,
            )

    async def _list_files(self) -> AgentResult:
        files = []
        for allowed in self._allowed_paths:
            p = Path(allowed)
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        files.append(str(f))
        content = "Files:\n" + "\n".join(files[:50]) if files else "No files found in workspace."
        return AgentResult(content=content, confidence=0.9, source_agent=self.name)

    async def _read_file(self, query: str) -> AgentResult:
        # Extract file path from query
        words = query.split()
        for word in words:
            if "/" in word or "\\" in word or "." in word:
                path = word.strip("'\"")
                if self._is_allowed(path) and Path(path).exists():
                    content = Path(path).read_text(encoding="utf-8", errors="replace")[:5000]
                    return AgentResult(content=content, confidence=0.9, source_agent=self.name)
        return AgentResult(content="Could not find the specified file.", confidence=0.3, source_agent=self.name)

    async def _write_file(self, query: str) -> AgentResult:
        """Extract filename and content from query, write to workspace."""
        import re
        # Expect format: write <path> <content> or save <path> \n<content>
        match = re.search(r'(?:write|save|create)\s+(\S+)\s+([\s\S]+)', query, re.IGNORECASE)
        if not match:
            return AgentResult(
                content=(
                    "請指定檔案路徑和內容，格式：\n"
                    "`write workspace/filename.txt 內容`\n\n"
                    "允許的路徑：" + ", ".join(self._allowed_paths)
                ),
                confidence=0.5, source_agent=self.name,
            )

        file_path = match.group(1).strip("'\"")
        content = match.group(2).strip()

        if not self._is_allowed(file_path):
            return AgentResult(
                content=f"⚠️ 路徑不在允許範圍內。允許目錄：{', '.join(self._allowed_paths)}",
                confidence=0.9, source_agent=self.name,
            )

        try:
            dest = Path(file_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            return AgentResult(
                content=f"✅ 已寫入 `{file_path}`（{len(content)} 字元）",
                confidence=0.9, source_agent=self.name,
            )
        except Exception as e:
            return AgentResult(
                content=f"❌ 寫檔失敗：{e}",
                confidence=0.3, source_agent=self.name,
            )
