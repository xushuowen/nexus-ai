"""PDF reader skill - extract text from local PDF files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


class PDFReaderSkill(BaseSkill):
    name = "pdf_reader"
    description = "PDF 閱讀器 — 讀取本地 PDF 檔案並提取文字"
    triggers = ["pdf", "讀pdf", "read pdf", "解析pdf", "open pdf", "PDF"]
    category = "document"
    requires_llm = False

    instructions = (
        "PDF 閱讀器：\n"
        "1. 讀取：「pdf 檔案路徑」\n"
        "2. 支援 data/ 和 workspace/ 目錄下的檔案\n"
        "3. 顯示頁數、文字內容（前 2000 字元）"
    )

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        # Extract file path from query
        for t in self.triggers:
            query = re.sub(re.escape(t), "", query, flags=re.IGNORECASE)
        file_path = query.strip().strip("\"'")

        if not file_path:
            return SkillResult(content="請提供 PDF 檔案路徑。", success=False, source=self.name)

        # Resolve path (check data/ and workspace/ directories)
        resolved = self._resolve_path(file_path)
        if not resolved:
            return SkillResult(
                content=f"找不到檔案: {file_path}\n\n📁 請確認檔案在 data/ 或 workspace/ 目錄中。",
                success=False, source=self.name,
            )

        try:
            from PyPDF2 import PdfReader
        except ImportError:
            return SkillResult(
                content="需要安裝 PyPDF2：`pip install PyPDF2`",
                success=False, source=self.name,
            )

        try:
            reader = PdfReader(str(resolved))
            num_pages = len(reader.pages)

            # Extract text from all pages
            all_text = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    all_text.append(f"--- 第 {i + 1} 頁 ---\n{text}")

            if not all_text:
                return SkillResult(
                    content=f"📄 {resolved.name}（{num_pages} 頁）\n\n⚠️ 無法提取文字（可能是掃描 PDF）。",
                    success=True, source=self.name,
                )

            full_text = "\n\n".join(all_text)
            # Truncate if too long
            if len(full_text) > 3000:
                full_text = full_text[:3000] + "\n\n... （已截斷，共 " + str(len("\n\n".join(all_text))) + " 字元）"

            result = (
                f"📄 **{resolved.name}**\n"
                f"📑 頁數: {num_pages}\n"
                f"📝 字數: {sum(len(t) for t in all_text)}\n\n"
                f"{full_text}"
            )
            return SkillResult(content=result, success=True, source=self.name)

        except Exception as e:
            return SkillResult(content=f"PDF 讀取失敗: {e}", success=False, source=self.name)

    def _resolve_path(self, file_path: str) -> Path | None:
        """Resolve PDF path within allowed directories."""
        candidates = [
            Path(file_path),
            config.data_dir() / file_path,
            config.data_dir() / "workspace" / file_path,
            Path.cwd() / file_path,
        ]

        for p in candidates:
            if p.exists() and p.suffix.lower() == ".pdf":
                # Security: ensure within allowed directories
                try:
                    allowed = [config.data_dir(), Path.cwd()]
                    if any(p.resolve().is_relative_to(a.resolve()) for a in allowed):
                        return p
                except (ValueError, RuntimeError):
                    continue
        return None
