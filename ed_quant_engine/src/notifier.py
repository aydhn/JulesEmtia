from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Awaitable, Callable

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

from src.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN
from src.logger import get_logger
import src.paper_db as db


logger = get_logger()
engine_paused = False
_panic_callback: Callable[[], Awaitable[None]] | None = None
_force_scan_callback: Callable[[], Awaitable[None]] | None = None
_telegram_warning_shown = False
_telegram_disabled_reason: str | None = None


def set_panic_callback(fn):
    global _panic_callback
    _panic_callback = fn


def set_force_scan_callback(fn):
    global _force_scan_callback
    _force_scan_callback = fn


def disable_telegram(reason: str) -> None:
    global _telegram_disabled_reason
    _telegram_disabled_reason = reason


def _is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered in {"test", "dummy", "placeholder", "changeme", "none"} or lowered.startswith("your_")


def _telegram_ready() -> bool:
    global _telegram_warning_shown
    if _telegram_disabled_reason:
        if not _telegram_warning_shown:
            logger.warning("Telegram notifications disabled: %s", _telegram_disabled_reason)
            _telegram_warning_shown = True
        return False
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        if not _telegram_warning_shown:
            logger.warning("Telegram credentials missing. Notifications disabled for this run.")
            _telegram_warning_shown = True
        return False
    if _is_placeholder(TELEGRAM_BOT_TOKEN) or _is_placeholder(ADMIN_CHAT_ID):
        if not _telegram_warning_shown:
            logger.warning("Telegram credentials look like placeholders. Notifications disabled for this run.")
            _telegram_warning_shown = True
        return False
    return True


async def send_telegram_message(message: str) -> None:
    if not _telegram_ready():
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="HTML")
    except Exception as exc:
        disable_telegram(f"message delivery failed: {exc}")
        logger.warning("Telegram message delivery failed; notifications disabled for this run: %s", exc)


async def send_telegram_document(file_path: str) -> None:
    path = Path(file_path)
    if not path.exists() or not _telegram_ready():
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        with path.open("rb") as handle:
            await bot.send_document(chat_id=ADMIN_CHAT_ID, document=handle)
    except Exception as exc:
        disable_telegram(f"document delivery failed: {exc}")
        logger.warning("Telegram document delivery failed; notifications disabled for this run: %s", exc)


def is_admin(update: Update) -> bool:
    return bool(update.effective_chat) and str(update.effective_chat.id) == str(ADMIN_CHAT_ID)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_admin(update) and update.message:
        await update.message.reply_text("ED Capital Quant Engine is ready.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.message:
        return
    balance = db.get_balance()
    open_trades = db.get_open_trades()
    audit = db.audit_trade_history()
    msg = f"<b>Status</b>\nBalance: ${balance:.2f}\nOpen positions: {len(open_trades)}\nSchema: {audit['schema_version']}"
    for trade in open_trades:
        msg += f"\n- #{trade['trade_id']} {trade['ticker']} {trade['direction']} @ {trade['entry_price']:.4f}"
    await update.message.reply_text(msg, parse_mode="HTML")


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.message:
        return
    global engine_paused
    engine_paused = True
    await update.message.reply_text("System paused. Open positions are still managed.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.message:
        return
    global engine_paused
    engine_paused = False
    await update.message.reply_text("System resumed.")


async def cmd_panic_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.message:
        return
    await update.message.reply_text("Panic close triggered.")
    if _panic_callback:
        asyncio.create_task(_panic_callback())
    else:
        await update.message.reply_text("Panic callback is not registered.")


async def cmd_force_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update) or not update.message:
        return
    await update.message.reply_text("Manual scan started.")
    if _force_scan_callback:
        asyncio.create_task(_force_scan_callback())
    else:
        await update.message.reply_text("Force scan callback is not registered.")


def get_telegram_application():
    if not _telegram_ready():
        return None
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("durum", cmd_status))
    app.add_handler(CommandHandler("durdur", cmd_pause))
    app.add_handler(CommandHandler("devam", cmd_resume))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_panic_close))
    app.add_handler(CommandHandler("tara", cmd_force_scan))
    return app
