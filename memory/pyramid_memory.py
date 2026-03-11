"""5-tier memory pyramid compression using SQLite.

Architecture:
    Tier 0 — Raw sessions (live, from SessionManager, last 72 h, no separate storage)
    Tier 1 — Daily summaries    → tier1_daily     (date TEXT PK)
    Tier 2 — Monthly summaries  → tier2_monthly   (month TEXT PK)
    Tier 3 — Yearly summaries   → tier3_yearly    (year TEXT PK)
    Tier 4 — Era summaries      → tier4_era       (era TEXT PK)
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from nexus import config

if TYPE_CHECKING:
    from nexus.memory.session import SessionManager
    from nexus.providers.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

# ── Context header template ──────────────────────────────────────────
_CONTEXT_HEADER = "=== 長期記憶（金字塔摘要）==="

# ── Summarization prompt templates ──────────────────────────────────
_DAILY_PROMPT_TMPL = """請將以下對話紀錄濃縮成一段 200 字以內的「每日摘要」，
保留重要決策、用戶偏好、解決的問題與關鍵資訊，使用繁體中文。

對話紀錄 ({date})：
{messages}

請直接輸出摘要內容，不要加標題或前置說明。"""

_MONTHLY_PROMPT_TMPL = """請將以下每日摘要整合成一段 300 字以內的「月度精華」，
突顯本月重要主題、重複模式與重要事件，使用繁體中文。

{month} 每日摘要：
{summaries}

請直接輸出月度精華，不要加標題或前置說明。"""

_YEARLY_PROMPT_TMPL = """請將以下月度精華整合成一段 400 字以內的「年度回顧」，
記錄全年重要里程碑、用戶目標與演進，使用繁體中文。

{year} 月度精華：
{summaries}

請直接輸出年度回顧，不要加標題或前置說明。"""

_ERA_PROMPT_TMPL = """請將以下年度回顧整合成一段 500 字以內的「時代總結」，
捕捉這個時代（{era}）的核心主題與深遠影響，使用繁體中文。

{summaries}

請直接輸出時代總結，不要加標題或前置說明。"""


class PyramidMemory:
    """5-tier memory pyramid with automatic compression via background task."""

    def __init__(
        self,
        session_manager: SessionManager,
        llm_provider: LLMProvider,
    ) -> None:
        self._session = session_manager
        self._llm = llm_provider
        self._lock = asyncio.Lock()
        self._scheduler_task: asyncio.Task | None = None
        self._conn: sqlite3.Connection | None = None

        cfg = config.load_config().get("pyramid_memory", {})
        db_path_str = cfg.get("db_path", "./data/pyramid.db")
        db_path = Path(db_path_str)
        if not db_path.is_absolute():
            db_path = config.data_dir() / db_path.name
        self._db_path = db_path

        self._compression_interval_hours: float = float(
            cfg.get("compression_interval_hours", 6)
        )
        self._daily_min_messages: int = int(cfg.get("daily_min_messages", 3))
        self._monthly_min_days: int = int(cfg.get("monthly_min_days", 3))
        self._context_max_chars: int = int(cfg.get("context_max_chars", 8000))
        self._retention_tier1_days: int = int(cfg.get("retention_tier1_days", 90))

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    async def initialize(self) -> None:
        """Create SQLite tables and start the background scheduler."""
        await asyncio.to_thread(self._create_tables)
        self.start_scheduler()
        logger.info("PyramidMemory initialised (db=%s)", self._db_path)

    def _create_tables(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tier1_daily (
                date       TEXT PRIMARY KEY,
                summary    TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tier2_monthly (
                month      TEXT PRIMARY KEY,
                summary    TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tier3_yearly (
                year       TEXT PRIMARY KEY,
                summary    TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tier4_era (
                era        TEXT PRIMARY KEY,
                summary    TEXT NOT NULL,
                created_at REAL NOT NULL
            );
        """)
        conn.commit()
        conn.close()
        # Keep a long-lived connection for reads
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)

    def start_scheduler(self) -> None:
        """Launch the asyncio background task that runs _compression_cycle() periodically."""
        if self._scheduler_task and not self._scheduler_task.done():
            return
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.debug("PyramidMemory scheduler started")

    async def _scheduler_loop(self) -> None:
        interval_secs = self._compression_interval_hours * 3600
        while True:
            try:
                await asyncio.sleep(interval_secs)
                await self._compression_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("PyramidMemory scheduler error: %s", e, exc_info=True)

    async def close(self) -> None:
        """Cancel scheduler and close SQLite connection."""
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        if self._conn:
            await asyncio.to_thread(self._conn.close)
            self._conn = None
        logger.info("PyramidMemory closed")

    # ──────────────────────────────────────────────
    # Compression cycle
    # ──────────────────────────────────────────────

    async def compress_now(self) -> None:
        """Force-run the compression cycle (for manual trigger / testing)."""
        await self._compression_cycle()

    async def _compression_cycle(self) -> None:
        """Idempotent compression: yesterday → tier1, last month → tier2, etc."""
        async with self._lock:
            now = datetime.now()
            logger.debug("PyramidMemory compression cycle starting at %s", now.isoformat())

            # Tier 1: yesterday
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            await self._maybe_compress_day(yesterday)

            # Tier 2: last calendar month (compress at start of new month)
            if now.day <= 3:
                # First three days of month → compress previous month
                first_of_month = now.replace(day=1)
                last_month_dt = first_of_month - timedelta(days=1)
                last_month = last_month_dt.strftime("%Y-%m")
                await self._maybe_compress_month(last_month)

            # Tier 3: last year (compress on Jan 1-3)
            if now.month == 1 and now.day <= 3:
                last_year = str(now.year - 1)
                await self._maybe_compress_year(last_year)

            # Tier 4: decade boundary (year ending in 0)
            if now.month == 1 and now.day <= 3 and now.year % 10 == 0:
                decade_start = now.year - 10
                era = f"{decade_start}s"
                await self._maybe_compress_era(era, decade_start, now.year - 1)

            # Retention: purge tier1 entries older than retention_tier1_days
            await self._purge_old_tier1()

            logger.debug("PyramidMemory compression cycle complete")

    # ── Tier 1: daily ─────────────────────────────

    async def _maybe_compress_day(self, date_str: str) -> None:
        """Compress a single day into tier1 if not already done and has enough messages."""
        exists = await asyncio.to_thread(self._tier1_exists, date_str)
        if exists:
            return

        messages = await self._get_messages_for_day(date_str)
        if len(messages) < self._daily_min_messages:
            logger.debug(
                "Skipping tier1 for %s: only %d messages (min %d)",
                date_str, len(messages), self._daily_min_messages,
            )
            return

        formatted = "\n".join(
            f"[{m['role'].upper()}] {m['content'][:500]}" for m in messages
        )
        prompt = _DAILY_PROMPT_TMPL.format(date=date_str, messages=formatted)
        try:
            summary = await self._llm.complete(prompt, source="pyramid_compression")
            await asyncio.to_thread(self._upsert_tier1, date_str, summary.strip())
            logger.info("PyramidMemory: compressed day %s → tier1 (%d chars)", date_str, len(summary))
        except Exception as e:
            logger.error("Tier1 compression failed for %s: %s", date_str, e)

    async def _get_messages_for_day(self, date_str: str) -> list[dict]:
        """Fetch all session messages from the given date (YYYY-MM-DD)."""
        if not self._session or not self._session._conn:
            return []
        # Convert date to UTC midnight timestamps
        try:
            dt_start = datetime.strptime(date_str, "%Y-%m-%d")
            dt_end = dt_start + timedelta(days=1)
            ts_start = dt_start.timestamp()
            ts_end = dt_end.timestamp()
        except ValueError:
            return []

        def _fetch():
            rows = self._session._conn.execute(
                "SELECT role, content, timestamp FROM sessions "
                "WHERE timestamp >= ? AND timestamp < ? "
                "ORDER BY timestamp ASC",
                (ts_start, ts_end),
            ).fetchall()
            return [{"role": r[0], "content": r[1], "timestamp": r[2]} for r in rows]

        return await asyncio.to_thread(_fetch)

    # ── Tier 2: monthly ───────────────────────────

    async def _maybe_compress_month(self, month_str: str) -> None:
        """Compress a calendar month's daily summaries into tier2."""
        exists = await asyncio.to_thread(self._tier2_exists, month_str)
        if exists:
            return

        summaries = await asyncio.to_thread(self._get_tier1_for_month, month_str)
        if len(summaries) < self._monthly_min_days:
            logger.debug(
                "Skipping tier2 for %s: only %d daily summaries (min %d)",
                month_str, len(summaries), self._monthly_min_days,
            )
            return

        formatted = "\n\n".join(
            f"[{date}]\n{text}" for date, text in summaries
        )
        prompt = _MONTHLY_PROMPT_TMPL.format(month=month_str, summaries=formatted)
        try:
            summary = await self._llm.complete(prompt, source="pyramid_compression")
            await asyncio.to_thread(self._upsert_tier2, month_str, summary.strip())
            logger.info("PyramidMemory: compressed month %s → tier2 (%d chars)", month_str, len(summary))
        except Exception as e:
            logger.error("Tier2 compression failed for %s: %s", month_str, e)

    # ── Tier 3: yearly ────────────────────────────

    async def _maybe_compress_year(self, year_str: str) -> None:
        """Compress all monthly summaries of a year into tier3."""
        exists = await asyncio.to_thread(self._tier3_exists, year_str)
        if exists:
            return

        summaries = await asyncio.to_thread(self._get_tier2_for_year, year_str)
        if not summaries:
            logger.debug("Skipping tier3 for %s: no monthly summaries", year_str)
            return

        formatted = "\n\n".join(
            f"[{month}]\n{text}" for month, text in summaries
        )
        prompt = _YEARLY_PROMPT_TMPL.format(year=year_str, summaries=formatted)
        try:
            summary = await self._llm.complete(prompt, source="pyramid_compression")
            await asyncio.to_thread(self._upsert_tier3, year_str, summary.strip())
            logger.info("PyramidMemory: compressed year %s → tier3 (%d chars)", year_str, len(summary))
        except Exception as e:
            logger.error("Tier3 compression failed for %s: %s", year_str, e)

    # ── Tier 4: era ───────────────────────────────

    async def _maybe_compress_era(self, era: str, start_year: int, end_year: int) -> None:
        """Compress yearly summaries for a decade into tier4."""
        exists = await asyncio.to_thread(self._tier4_exists, era)
        if exists:
            return

        summaries = await asyncio.to_thread(
            self._get_tier3_for_era, start_year, end_year
        )
        if not summaries:
            logger.debug("Skipping tier4 for era %s: no yearly summaries", era)
            return

        formatted = "\n\n".join(
            f"[{year}]\n{text}" for year, text in summaries
        )
        prompt = _ERA_PROMPT_TMPL.format(era=era, summaries=formatted)
        try:
            summary = await self._llm.complete(prompt, source="pyramid_compression")
            await asyncio.to_thread(self._upsert_tier4, era, summary.strip())
            logger.info("PyramidMemory: compressed era %s → tier4 (%d chars)", era, len(summary))
        except Exception as e:
            logger.error("Tier4 compression failed for era %s: %s", era, e)

    # ──────────────────────────────────────────────
    # Context building
    # ──────────────────────────────────────────────

    async def build_context(self) -> str:
        """Return a formatted long-term memory context string, capped at context_max_chars."""
        parts: list[str] = [_CONTEXT_HEADER]
        char_budget = self._context_max_chars - len(_CONTEXT_HEADER) - 10

        # Tier 3: most recent yearly summary
        yearly = await asyncio.to_thread(self._get_recent_tier3, 1)
        for year, text in yearly:
            snippet = text[: min(600, char_budget)]
            line = f"\n[年度回顧 {year}] {snippet}"
            if char_budget - len(line) < 0:
                break
            parts.append(line)
            char_budget -= len(line)

        # Tier 2: last 3 months
        monthly = await asyncio.to_thread(self._get_recent_tier2, 3)
        for month, text in monthly:
            snippet = text[: min(400, char_budget)]
            line = f"\n[月度精華 {month}] {snippet}"
            if char_budget - len(line) < 0:
                break
            parts.append(line)
            char_budget -= len(line)

        # Tier 1: last 7 days
        daily = await asyncio.to_thread(self._get_recent_tier1, 7)
        for date, text in daily:
            snippet = text[: min(300, char_budget)]
            line = f"\n[每日摘要 {date}] {snippet}"
            if char_budget - len(line) < 0:
                break
            parts.append(line)
            char_budget -= len(line)

        result = "".join(parts)
        if len(result) <= len(_CONTEXT_HEADER) + 2:
            return ""  # nothing to inject
        return result

    # ──────────────────────────────────────────────
    # Retention
    # ──────────────────────────────────────────────

    async def _purge_old_tier1(self) -> None:
        cutoff_dt = datetime.now() - timedelta(days=self._retention_tier1_days)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d")
        deleted = await asyncio.to_thread(self._delete_tier1_before, cutoff_str)
        if deleted:
            logger.info("PyramidMemory: purged %d tier1 entries older than %s", deleted, cutoff_str)

    # ──────────────────────────────────────────────
    # SQLite helpers (synchronous, run via to_thread)
    # ──────────────────────────────────────────────

    def _conn_or_raise(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("PyramidMemory: SQLite connection not initialised")
        return self._conn

    # Existence checks
    def _tier1_exists(self, date: str) -> bool:
        row = self._conn_or_raise().execute(
            "SELECT 1 FROM tier1_daily WHERE date = ?", (date,)
        ).fetchone()
        return row is not None

    def _tier2_exists(self, month: str) -> bool:
        row = self._conn_or_raise().execute(
            "SELECT 1 FROM tier2_monthly WHERE month = ?", (month,)
        ).fetchone()
        return row is not None

    def _tier3_exists(self, year: str) -> bool:
        row = self._conn_or_raise().execute(
            "SELECT 1 FROM tier3_yearly WHERE year = ?", (year,)
        ).fetchone()
        return row is not None

    def _tier4_exists(self, era: str) -> bool:
        row = self._conn_or_raise().execute(
            "SELECT 1 FROM tier4_era WHERE era = ?", (era,)
        ).fetchone()
        return row is not None

    # Upserts
    def _upsert_tier1(self, date: str, summary: str) -> None:
        conn = self._conn_or_raise()
        conn.execute(
            "INSERT OR REPLACE INTO tier1_daily (date, summary, created_at) VALUES (?, ?, ?)",
            (date, summary, time.time()),
        )
        conn.commit()

    def _upsert_tier2(self, month: str, summary: str) -> None:
        conn = self._conn_or_raise()
        conn.execute(
            "INSERT OR REPLACE INTO tier2_monthly (month, summary, created_at) VALUES (?, ?, ?)",
            (month, summary, time.time()),
        )
        conn.commit()

    def _upsert_tier3(self, year: str, summary: str) -> None:
        conn = self._conn_or_raise()
        conn.execute(
            "INSERT OR REPLACE INTO tier3_yearly (year, summary, created_at) VALUES (?, ?, ?)",
            (year, summary, time.time()),
        )
        conn.commit()

    def _upsert_tier4(self, era: str, summary: str) -> None:
        conn = self._conn_or_raise()
        conn.execute(
            "INSERT OR REPLACE INTO tier4_era (era, summary, created_at) VALUES (?, ?, ?)",
            (era, summary, time.time()),
        )
        conn.commit()

    # Data fetches for compression inputs
    def _get_tier1_for_month(self, month_str: str) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT date, summary FROM tier1_daily "
            "WHERE date LIKE ? ORDER BY date ASC",
            (f"{month_str}-%",),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _get_tier2_for_year(self, year_str: str) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT month, summary FROM tier2_monthly "
            "WHERE month LIKE ? ORDER BY month ASC",
            (f"{year_str}-%",),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def _get_tier3_for_era(self, start_year: int, end_year: int) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT year, summary FROM tier3_yearly "
            "WHERE CAST(year AS INTEGER) >= ? AND CAST(year AS INTEGER) <= ? "
            "ORDER BY year ASC",
            (start_year, end_year),
        ).fetchall()
        return [(r[0], r[1]) for r in rows]

    # Data fetches for context building
    def _get_recent_tier1(self, n: int) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT date, summary FROM tier1_daily ORDER BY date DESC LIMIT ?",
            (n,),
        ).fetchall()
        return list(reversed([(r[0], r[1]) for r in rows]))

    def _get_recent_tier2(self, n: int) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT month, summary FROM tier2_monthly ORDER BY month DESC LIMIT ?",
            (n,),
        ).fetchall()
        return list(reversed([(r[0], r[1]) for r in rows]))

    def _get_recent_tier3(self, n: int) -> list[tuple[str, str]]:
        rows = self._conn_or_raise().execute(
            "SELECT year, summary FROM tier3_yearly ORDER BY year DESC LIMIT ?",
            (n,),
        ).fetchall()
        return list(reversed([(r[0], r[1]) for r in rows]))

    # Retention
    def _delete_tier1_before(self, cutoff_date: str) -> int:
        conn = self._conn_or_raise()
        result = conn.execute(
            "DELETE FROM tier1_daily WHERE date < ?", (cutoff_date,)
        )
        conn.commit()
        return result.rowcount
