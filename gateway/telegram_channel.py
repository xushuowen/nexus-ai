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
        # Build whitelist: always include owner (TELEGRAM_CHAT_ID),
        # plus any extra IDs from TELEGRAM_ALLOWED_USERS.
        self._allowed_users: set[int] = set()
        owner_id = os.getenv("TELEGRAM_CHAT_ID", "").strip().lstrip("-")
        if owner_id.isdigit():
            self._allowed_users.add(int(owner_id))
        extra = os.getenv("TELEGRAM_ALLOWED_USERS", "").strip()
        if extra:
            for uid in extra.split(","):
                uid = uid.strip().lstrip("-")
                if uid.isdigit():
                    self._allowed_users.add(int(uid))
        if self._allowed_users:
            logger.info(f"Telegram whitelist: {self._allowed_users}")
        else:
            logger.warning(
                "Telegram: no whitelist configured "
                "(set TELEGRAM_CHAT_ID or TELEGRAM_ALLOWED_USERS). "
                "Bot will reject all incoming messages."
            )

    def _is_user_allowed(self, chat_id: int) -> bool:
        """Check if chat_id is whitelisted. Defaults to deny-all for safety."""
        if not self._allowed_users:
            return False  # no whitelist → deny everyone
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
                "*對話方式：*\n"
                "• 直接打字對話\n"
                "• 傳送📷圖片 → 自動分析（OCR/描述）\n"
                "• 傳送📄PDF → 自動提取文字\n"
                "• 傳送📝文字檔 → 自動讀取內容\n"
                "• 圖片/文件 + 說明文字 → 針對性分析\n\n"
                "*系統功能：*\n"
                "• 多路徑推理 + 自我驗證\n"
                "• 4 層記憶系統\n"
                "• 新聞、天氣、提醒、排程等技能\n"
                "• Token 預算控制\n\n"
                "*指令：* /status /budget /reset /help",
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

        async def cmd_chatid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            chat_id = update.effective_chat.id
            await update.message.reply_text(
                f"📋 你的 Chat ID 是：\n`{chat_id}`\n\n"
                "請把這個數字填入 `.env` 的 `TELEGRAM_CHAT_ID=`",
                parse_mode="Markdown",
            )

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

        # ── Photo handler ──
        async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not update.message:
                return
            chat_id = update.effective_chat.id
            if not self._is_user_allowed(chat_id):
                await update.message.reply_text("⛔ 未授權的用戶。")
                return
            if not self._orchestrator:
                await update.message.reply_text("⏳ 系統尚未就緒，請稍後再試。")
                return

            caption = update.message.caption or "請描述這張圖片的內容。"
            session_id = f"tg_{chat_id}"
            await update.message.chat.send_action("typing")

            import time as _time
            from pathlib import Path as _Path

            upload_dir = _Path(__file__).parent.parent / "data" / "tg_uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            # Download highest-resolution photo
            photo = update.message.photo[-1]
            tg_file = await photo.get_file()
            img_path = upload_dir / f"photo_{int(_time.time())}_{photo.file_id[-8:]}.jpg"
            await tg_file.download_to_drive(str(img_path))
            logger.info(f"Photo saved: {img_path}")

            final_answer = ""
            try:
                async for event in self._orchestrator.process(
                    caption, session_id,
                    extra_context={"has_image": True, "image_path": str(img_path)},
                    force_agent="vision",
                ):
                    if event.event_type == "final_answer":
                        final_answer = event.content
            except Exception as e:
                logger.error(f"Photo processing error: {e}", exc_info=True)
                final_answer = f"❌ 圖片分析失敗: {e}"
            finally:
                try:
                    img_path.unlink(missing_ok=True)
                except Exception:
                    pass

            for chunk in self._split_message(final_answer or "（無法分析圖片）", 4000):
                await update.message.reply_text(chunk)

        # ── Document handler ──
        async def handle_document(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            if not update.message or not update.message.document:
                return
            chat_id = update.effective_chat.id
            if not self._is_user_allowed(chat_id):
                await update.message.reply_text("⛔ 未授權的用戶。")
                return
            if not self._orchestrator:
                await update.message.reply_text("⏳ 系統尚未就緒，請稍後再試。")
                return

            doc = update.message.document
            caption = update.message.caption or ""
            session_id = f"tg_{chat_id}"
            await update.message.chat.send_action("typing")

            import time as _time
            from pathlib import Path as _Path

            upload_dir = _Path(__file__).parent.parent / "data" / "tg_uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)

            file_name = doc.file_name or "file"
            ext = _Path(file_name).suffix.lower()
            mime = doc.mime_type or ""

            IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
            TEXT_EXTS  = {".txt", ".md", ".csv", ".json", ".log", ".py",
                          ".js", ".ts", ".html", ".css", ".xml", ".yaml", ".yml"}

            save_path = upload_dir / f"{int(_time.time())}_{file_name}"
            tg_file = await doc.get_file()
            await tg_file.download_to_drive(str(save_path))
            logger.info(f"Document saved: {save_path} ({mime})")

            final_answer = ""
            try:
                if mime.startswith("image/") or ext in IMAGE_EXTS:
                    # ── Image document → Vision agent ──
                    user_q = caption or "請描述這張圖片的內容。"
                    async for event in self._orchestrator.process(
                        user_q, session_id,
                        extra_context={"has_image": True, "image_path": str(save_path)},
                        force_agent="vision",
                    ):
                        if event.event_type == "final_answer":
                            final_answer = event.content
                    save_path.unlink(missing_ok=True)

                elif mime == "application/pdf" or ext == ".pdf":
                    # ── PDF → pdf_reader skill ──
                    query = f"pdf {save_path}"
                    if caption:
                        query += f"\n{caption}"
                    async for event in self._orchestrator.process(query, session_id):
                        if event.event_type == "final_answer":
                            final_answer = event.content
                    # Keep PDF for possible re-use; user can delete manually

                elif mime.startswith("text/") or ext in TEXT_EXTS:
                    # ── Text file → read and inject into prompt ──
                    try:
                        content = save_path.read_text(encoding="utf-8", errors="replace")[:6000]
                    except Exception:
                        content = "(無法讀取檔案內容)"
                    save_path.unlink(missing_ok=True)
                    query = f"【檔案：{file_name}】\n{content}"
                    if caption:
                        query = f"{caption}\n\n{query}"
                    async for event in self._orchestrator.process(query, session_id):
                        if event.event_type == "final_answer":
                            final_answer = event.content

                else:
                    save_path.unlink(missing_ok=True)
                    final_answer = (
                        f"⚠️ 不支援的檔案格式：`{ext or mime}`\n\n"
                        "目前支援：\n"
                        "• 📷 圖片（jpg/png/webp/gif）\n"
                        "• 📄 PDF 文件\n"
                        "• 📝 文字檔（txt/md/csv/json/py 等）"
                    )

            except Exception as e:
                logger.error(f"Document processing error: {e}", exc_info=True)
                final_answer = f"❌ 檔案處理失敗: {e}"
                try:
                    save_path.unlink(missing_ok=True)
                except Exception:
                    pass

            for chunk in self._split_message(final_answer or "（無法處理檔案）", 4000):
                await update.message.reply_text(chunk)

        # Register handlers
        self._app.add_handler(CommandHandler("start", cmd_start))
        self._app.add_handler(CommandHandler("help", cmd_help))
        self._app.add_handler(CommandHandler("status", cmd_status))
        self._app.add_handler(CommandHandler("budget", cmd_budget))
        self._app.add_handler(CommandHandler("reset", cmd_reset))
        self._app.add_handler(CommandHandler("chatid", cmd_chatid))
        self._app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        self._app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
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
                BotCommand("chatid", "查詢我的 Chat ID"),
                BotCommand("help", "使用說明"),
            ])
        except Exception:
            pass

        self._running = True
        logger.info("✅ Telegram bot started! Send a message to your bot.")

        # Add error handler to suppress Conflict warnings on rapid restart
        async def _on_error(update, ctx) -> None:
            from telegram.error import Conflict
            if isinstance(ctx.error, Conflict):
                logger.warning("Telegram: Conflict detected (old instance still alive), will auto-recover in ~10s")
                await asyncio.sleep(10)
            else:
                logger.warning("Telegram error: %s", ctx.error)

        self._app.add_error_handler(_on_error)

        # Start polling (non-blocking); wait 5s first to let old instance disconnect
        await self._app.initialize()
        await self._app.start()
        await asyncio.sleep(5)
        await self._app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )

    async def send_to_owner(self, text: str) -> bool:
        """Proactively send a message to the owner (e.g. morning report)."""
        chat_id_str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if not chat_id_str or not self._app:
            logger.warning("send_to_owner: TELEGRAM_CHAT_ID not set or bot not started")
            return False
        try:
            for chunk in self._split_message(text, 4000):
                await self._app.bot.send_message(chat_id=int(chat_id_str), text=chunk)
            logger.info("send_to_owner: message sent successfully")
            return True
        except Exception as e:
            logger.error(f"send_to_owner failed: {e}")
            return False

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
