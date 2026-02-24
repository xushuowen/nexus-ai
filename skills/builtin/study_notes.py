"""Study notes skill - organized note-taking system for PT students."""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any

from nexus.skills.skill_base import BaseSkill, SkillResult
from nexus import config


# Default PT subject categories
PT_SUBJECTS = {
    "解剖學": "anatomy",
    "anatomy": "anatomy",
    "生理學": "physiology",
    "physiology": "physiology",
    "運動學": "kinesiology",
    "kinesiology": "kinesiology",
    "治療學": "therapeutics",
    "therapeutics": "therapeutics",
    "病理學": "pathology",
    "pathology": "pathology",
    "骨科": "orthopedics",
    "orthopedics": "orthopedics",
    "神經": "neurology",
    "neurology": "neurology",
    "心肺": "cardiopulmonary",
    "cardiopulmonary": "cardiopulmonary",
    "小兒": "pediatrics",
    "pediatrics": "pediatrics",
    "老人": "geriatrics",
    "geriatrics": "geriatrics",
    "生物力學": "biomechanics",
    "biomechanics": "biomechanics",
    "電療": "electrotherapy",
    "徒手治療": "manual_therapy",
}


class StudyNotesSkill(BaseSkill):
    name = "study_notes"
    description = "筆記系統 — 物理治療專用分科筆記、複習、搜尋"
    triggers = ["筆記", "note", "複習", "review notes", "整理", "study", "考試", "exam", "notes"]
    intent_patterns = [
        r"(記一下|記錄|紀錄).{2,40}",
        r"(解剖學|生理學|運動學|治療學|病理學|骨科|神經|心肺|小兒|老人|生物力學|電療|徒手治療).{2,40}",
        r"(複習|背一下|練習).{0,5}(解剖|骨科|神經|心肺|生理|運動學)",
        r"(考試|出題|練習題).{0,10}(解剖|骨科|神經|物理治療)",
        r"(我的|看我的|列出).{0,5}(筆記|科目|notes)",
    ]
    category = "academic"
    requires_llm = False

    instructions = (
        "PT 筆記系統：\n"
        "1. 新增：「筆記 解剖學 肩關節旋轉肌群的組成」\n"
        "2. 搜尋：「筆記 搜尋 旋轉肌」\n"
        "3. 列出科目：「筆記 科目」\n"
        "4. 複習：「筆記 複習 解剖學」\n"
        "5. 生成題目：「筆記 考試 解剖學」（需要 LLM）"
    )

    def __init__(self) -> None:
        self._db_path = config.data_dir() / "study_notes.db"
        self._conn: sqlite3.Connection | None = None

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                subject TEXT NOT NULL,
                chapter TEXT DEFAULT '',
                content TEXT NOT NULL,
                tags TEXT DEFAULT '',
                timestamp REAL NOT NULL,
                date TEXT NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_subject ON notes(subject)")
        self._conn.commit()

    async def execute(self, query: str, context: dict[str, Any]) -> SkillResult:
        text = query.lower()

        if any(k in text for k in ["搜尋", "search", "找"]):
            return self._search(query)
        elif any(k in text for k in ["科目", "subjects", "分類", "categories"]):
            return self._list_subjects()
        elif any(k in text for k in ["複習", "review", "最近"]):
            return self._review(query)
        elif any(k in text for k in ["考試", "exam", "題目", "quiz"]):
            return await self._generate_quiz(query, context)
        elif any(k in text for k in ["匯出", "export"]):
            return self._export(query)
        else:
            return self._add(query)

    def _add(self, content: str) -> SkillResult:
        """Add a new note."""
        for t in self.triggers:
            content = content.replace(t, "").strip()
        content = content.strip(" ：:")

        # Detect subject
        subject = "general"
        for keyword, subj in PT_SUBJECTS.items():
            if keyword in content.lower():
                subject = subj
                content = re.sub(re.escape(keyword), "", content, flags=re.IGNORECASE).strip()
                break

        if not content or len(content) < 3:
            return SkillResult(
                content="請輸入筆記內容，例如：「筆記 解剖學 肩關節旋轉肌群包括棘上肌、棘下肌、小圓肌、肩胛下肌」",
                success=False, source=self.name,
            )

        now = time.time()
        date_str = time.strftime("%Y-%m-%d")
        self._conn.execute(
            "INSERT INTO notes (subject, content, timestamp, date) VALUES (?, ?, ?, ?)",
            (subject, content, now, date_str),
        )
        self._conn.commit()

        subject_zh = self._subject_to_zh(subject)
        return SkillResult(
            content=f"📝 筆記已儲存 [{subject_zh}]\n\n> {content}",
            success=True, source=self.name,
        )

    def _search(self, query: str) -> SkillResult:
        """Search notes by keyword."""
        for prefix in ["搜尋", "search", "找", "筆記"]:
            query = query.replace(prefix, "").strip()
        query = query.strip()

        if not query:
            return SkillResult(content="請提供搜尋關鍵字。", success=False, source=self.name)

        rows = self._conn.execute(
            "SELECT id, subject, content, date FROM notes WHERE content LIKE ? ORDER BY timestamp DESC LIMIT 15",
            (f"%{query}%",),
        ).fetchall()

        if not rows:
            return SkillResult(content=f"找不到包含「{query}」的筆記。", success=True, source=self.name)

        lines = [f"🔍 搜尋「{query}」找到 {len(rows)} 筆：\n"]
        for nid, subject, content, date in rows:
            subject_zh = self._subject_to_zh(subject)
            lines.append(f"  [{nid}] 📖 {subject_zh} | {date}")
            lines.append(f"       {content[:100]}")
            lines.append("")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _list_subjects(self) -> SkillResult:
        """List all subjects and note counts."""
        rows = self._conn.execute(
            "SELECT subject, COUNT(*) as cnt FROM notes GROUP BY subject ORDER BY cnt DESC"
        ).fetchall()

        if not rows:
            return SkillResult(content="還沒有任何筆記。開始記錄吧！", success=True, source=self.name)

        total = sum(r[1] for r in rows)
        lines = [f"📚 **筆記科目統計**（共 {total} 筆）\n"]
        for subject, count in rows:
            subject_zh = self._subject_to_zh(subject)
            lines.append(f"  📖 {subject_zh}: {count} 筆")

        lines.append(f"\n💡 輸入「筆記 複習 解剖學」可複習特定科目")
        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _review(self, query: str) -> SkillResult:
        """Review notes for a subject."""
        subject = "general"
        for keyword, subj in PT_SUBJECTS.items():
            if keyword in query.lower():
                subject = subj
                break

        rows = self._conn.execute(
            "SELECT id, content, date FROM notes WHERE subject = ? ORDER BY timestamp DESC LIMIT 10",
            (subject,),
        ).fetchall()

        if not rows:
            subject_zh = self._subject_to_zh(subject)
            return SkillResult(content=f"「{subject_zh}」還沒有筆記。", success=True, source=self.name)

        subject_zh = self._subject_to_zh(subject)
        lines = [f"📖 **{subject_zh}複習**（{len(rows)} 筆）\n"]
        for nid, content, date in rows:
            lines.append(f"[{date}] {content[:200]}")
            lines.append("")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    async def _generate_quiz(self, query: str, context: dict[str, Any]) -> SkillResult:
        """Generate quiz questions from notes (requires LLM)."""
        llm = context.get("llm")

        # Find subject
        subject = "general"
        for keyword, subj in PT_SUBJECTS.items():
            if keyword in query.lower():
                subject = subj
                break

        rows = self._conn.execute(
            "SELECT content FROM notes WHERE subject = ? ORDER BY RANDOM() LIMIT 10",
            (subject,),
        ).fetchall()

        if not rows:
            subject_zh = self._subject_to_zh(subject)
            return SkillResult(content=f"「{subject_zh}」還沒有筆記，無法生成題目。", success=True, source=self.name)

        notes_text = "\n".join(r[0] for r in rows)
        subject_zh = self._subject_to_zh(subject)

        if not llm:
            return SkillResult(
                content=f"📖 {subject_zh}筆記（{len(rows)} 筆）:\n\n{notes_text[:1000]}\n\n💡 連接 LLM 可自動生成複習題目。",
                success=True, source=self.name,
            )

        prompt = (
            f"根據以下物理治療「{subject_zh}」的筆記內容，用繁體中文生成 5 題選擇題（含答案和解析）。\n"
            f"格式：題目 → 4 個選項 → 答案 → 簡短解析\n\n"
            f"筆記內容：\n{notes_text[:2000]}"
        )

        try:
            quiz = await llm.complete(prompt, task_type="simple_tasks", source="study_notes_quiz")
            return SkillResult(
                content=f"📝 **{subject_zh}考試題目**\n\n{quiz}",
                success=True, source=self.name,
            )
        except Exception as e:
            return SkillResult(content=f"題目生成失敗: {e}", success=False, source=self.name)

    def _export(self, query: str) -> SkillResult:
        """Export notes for a subject."""
        subject = "general"
        for keyword, subj in PT_SUBJECTS.items():
            if keyword in query.lower():
                subject = subj
                break

        rows = self._conn.execute(
            "SELECT content, date FROM notes WHERE subject = ? ORDER BY timestamp",
            (subject,),
        ).fetchall()

        if not rows:
            return SkillResult(content="沒有筆記可匯出。", success=True, source=self.name)

        subject_zh = self._subject_to_zh(subject)
        lines = [f"# {subject_zh} 筆記\n"]
        current_date = ""
        for content, date in rows:
            if date != current_date:
                lines.append(f"\n## {date}\n")
                current_date = date
            lines.append(f"- {content}")

        return SkillResult(content="\n".join(lines), success=True, source=self.name)

    def _subject_to_zh(self, subject: str) -> str:
        """Convert subject code to Chinese name."""
        zh_map = {
            "anatomy": "解剖學", "physiology": "生理學", "kinesiology": "運動學",
            "therapeutics": "治療學", "pathology": "病理學", "orthopedics": "骨科",
            "neurology": "神經", "cardiopulmonary": "心肺", "pediatrics": "小兒",
            "geriatrics": "老人", "biomechanics": "生物力學", "electrotherapy": "電療",
            "manual_therapy": "徒手治療", "general": "一般",
        }
        return zh_map.get(subject, subject)

    async def shutdown(self) -> None:
        if self._conn:
            self._conn.close()
