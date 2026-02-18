"""Telegram bot channel - allows interaction via Telegram on mobile."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from nexus import config

logger = logging.getLogger(__name__)


class TelegramChannel:
    """Telegram bot integration for mobile access.

    Usage:
    1. Talk to @BotFather on Telegram, send /newbot
    2. Copy the token to .env as TELEGRAM_BOT_TOKEN
    3. Start Nexus, the bot will automatically begin polling
    """

    def __init__(self) -> None:
        self._orchestrator = None
        self._memory = None
        self._budget = None
        self._app = None
        self._running = False
        # Whitelist: comma-separated chat IDs in env var
        raw = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()
        self._allowed_users: set[int] = set()
        if raw:
            for uid in raw.split(","):
                uid = uid.strip()
                if uid.isdigit():
                    self._allowed_users.add(int(uid))
            logger.info(f"Telegram whitelist: {self._allowed_users}")

    def _is_user_allowed(self, chat_id: int) -> bool:
        """Check if user is allowed. If no whitelist set, allow all."""
        if not self._allowed_users:
            return True
        return chat_id in self._allowed_users

    def set_orchestrator(self, orchestrator) -> None:
        self._orchestrator = orchestrator

    def set_memory(self, memory) -> None:
        self._memory = memory

    def set_budget(self, budget) -> None:
        self._budget = budget

    async def start(self) -> None:
        token = (
            config.get("gateway.telegram.token", "")
            or os.getenv("TELEGRAM_BOT_TOKEN", "")
        )
        if not token:
            logger.info(
                "Telegram disabled. To enable:\n"
                "  1. Talk to @BotFather on Telegram\n"
                "  2. Create a bot with /newbot\n"
                "  3. Put the token in .env as TELEGRAM_BOT_TOKEN=xxx"
            )
            return

        try:
            from telegram import Update, BotCommand
            from telegram.ext import (
                ApplicationBuilder,
                CommandHandler,
                MessageHandler,
                filters,
                ContextTypes,
            )
        except ImportError:
            logger.error(
                "python-telegram-bot not installed! Run:\n"
                "  pip install python-telegram-bot"
            )
            return

        # Build bot application
        self._app = ApplicationBuilder().token(token).build()

        # ── Command handlers ──
        async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "🧠 *Nexus AI* 已上線！\n\n"
                "直接傳送訊息即可對話。\n\n"
                "指令:\n"
                "/status - 查看系統狀態\n"
                "/reset - 重置對話\n"
                "/budget - 查看 token 預算\n"
                "/help - 說明",
                parse_mode="Markdown",
            )

        async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(
                "🧠 *Nexus AI 說明*\n\n"
                "這是一個多代理 AI 助理，具備:\n"
                "• 多路徑推理 + 自我驗證\n"
                "• 4 層記憶系統（會記住你教的東西）\n"
                "• 好奇心引擎（會自主探索知識）\n"
                "• Token 預算控制（不會燒爆 API）\n\n"
                "直接打字就能對話！",
                parse_mode="Markdown",
            )

        async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            parts = ["📊 *系統狀態*\n"]
            if self._budget:
                s = self._budget.get_status()
                pct = (1 - s["usage_ratio"]) * 100
                parts.append(f"💰 Token: {s['tokens_used']:,} / {s['daily_limit']:,}")
                parts.append(f"🔋 剩餘: {pct:.1f}%")
                parts.append(f"📨 今日請求: {s['request_count']}")
                parts.append(f"🔬 好奇心剩餘: {s['curiosity_ops_remaining']}")
            if self._memory:
                parts.append(f"\n💾 工作記憶: {self._memory.working.size} slots")
            await update.message.reply_text("\n".join(parts), parse_mode="Markdown")

        async def cmd_budget(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not self._budget:
                await update.message.reply_text("Budget controller not available.")
                return
            s = self._budget.get_status()
            bar_len = 20
            filled = int(s["usage_ratio"] * bar_len)
            bar = "█" * filled + "░" * (bar_len - filled)
            await update.message.reply_text(
                f"📊 *Token 預算*\n\n"
                f"`[{bar}]` {s['usage_ratio']*100:.1f}%\n\n"
                f"已用: {s['tokens_used']:,}\n"
                f"上限: {s['daily_limit']:,}\n"
                f"剩餘: {s['tokens_remaining']:,}",
                parse_mode="Markdown",
            )

        async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            session_id = f"tg_{chat_id}"
            if self._memory:
                await self._memory.session.clear_session(session_id)
                self._memory.working.clear()
            await update.message.reply_text("🔄 對話已重置。")

        # ── Message handler ──
        async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not update.message or not update.message.text:
                return

            chat_id = update.effective_chat.id
            if not self._is_user_allowed(chat_id):
                await update.message.reply_text("⛔ 未授權的用戶。請聯繫管理員。")
                logger.warning(f"Unauthorized Telegram user: {chat_id}")
                return

            if not self._orchestrator:
                await update.message.reply_text("⏳ 系統尚未就緒，請稍後再試。")
                return

            chat_id = update.effective_chat.id
            session_id = f"tg_{chat_id}"
            user_text = update.message.text

            logger.info(f"📩 Telegram message from {chat_id}: {user_text[:80]}")

            # Send "typing" indicator
            await update.message.chat.send_action("typing")

            # Process through orchestrator
            final_answer = ""
            thinking_parts = []

            try:
                logger.info("Starting orchestrator.process()...")
                async for event in self._orchestrator.process(user_text, session_id):
                    logger.info(f"Event: {event.event_type} | {event.content[:100] if event.content else '(empty)'}")
                    if event.event_type == "final_answer":
                        final_answer = event.content
                    elif event.event_type in ("hypothesis", "selected", "verified"):
                        thinking_parts.append(event.content)
                logger.info(f"Orchestrator done. Answer length: {len(final_answer)}")
            except Exception as e:
                logger.error(f"Telegram processing error: {e}", exc_info=True)
                final_answer = f"❌ 處理錯誤: {e}"

            if not final_answer:
                final_answer = "（沒有生成回應）"

            # Send response (split if too long for Telegram's 4096 char limit)
            logger.info(f"Sending reply to Telegram ({len(final_answer)} chars)...")
            for chunk in self._split_message(final_answer, 4000):
                try:
                    await update.message.reply_text(chunk)
                    logger.info("✅ Reply sent successfully")
                except Exception as e:
                    logger.error(f"Telegram send error: {e}", exc_info=True)

        # Register handlers
        self._app.add_handler(CommandHandler("start", cmd_start))
        self._app.add_handler(CommandHandler("help", cmd_help))
        self._app.add_handler(CommandHandler("status", cmd_status))
        self._app.add_handler(CommandHandler("budget", cmd_budget))
        self._app.add_handler(CommandHandler("reset", cmd_reset))
        self._app.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        )

        # Set bot commands menu
        try:
            await self._app.bot.set_my_commands([
                BotCommand("start", "啟動 Nexus AI"),
                BotCommand("status", "系統狀態"),
                BotCommand("budget", "Token 預算"),
                BotCommand("reset", "重置對話"),
                BotCommand("help", "使用說明"),
            ])
        except Exception:
            pass

        self._running = True
        logger.info("✅ Telegram bot started! Send a message to your bot.")

        # Start polling (non-blocking)
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)

    async def stop(self) -> None:
        self._running = False
        if self._app:
            try:
                await self._app.updater.stop()
                await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                logger.warning(f"Telegram shutdown: {e}")

    @staticmethod
    def _split_message(text: str, max_len: int = 4000) -> list[str]:
        """Split long messages for Telegram's character limit."""
        if len(text) <= max_len:
            return [text]
        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            # Try to split at newline
            split_at = text.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = max_len
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
