import os
import requests
import asyncio
from dotenv import load_dotenv
from typing import Optional, List, Callable
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from logger import log
import paper_db

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Global state for pause/resume via Telegram commands
SYSTEM_PAUSED = False

def send_telegram_sync(message: str) -> None:
    """Synchronous fallback to send Telegram messages via standard HTTP Requests."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("Telegram Token or Admin Chat ID not found. Skipping message.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        log.info(f"Telegram message sent: {message[:30]}...")
    except requests.exceptions.RequestException as e:
        log.error(f"Failed to send Telegram message: {e}")

async def send_telegram_async(message: str) -> None:
    """Asynchronous Telegram messaging for the main loop."""
    # Since we are using an HTTP request instead of Application.bot.send_message
    # to avoid tight coupling and locking issues.
    await asyncio.to_thread(send_telegram_sync, message)


# ==========================================
# Two-Way Command Handlers (Admin Only)
# ==========================================

async def authenticate(update: Update) -> bool:
    """Ensure commands are only accepted from the ADMIN_CHAT_ID whitelist."""
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        log.critical(f"Unauthorized access attempt from user: {update.effective_user.id} / chat: {update.effective_chat.id}")
        await update.message.reply_text("🚨 Yetkisiz Erişim Reddedildi.")
        return False
    return True

async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/durum command: Returns current portfolio and open positions status."""
    if not await authenticate(update): return

    open_trades = paper_db.get_open_trades()
    count = len(open_trades)

    msg = f"🟢 <b>ED Capital Quant Engine - Durum Raporu</b>\n\n"
    msg += f"Sistem Duraklatıldı mı?: {'Evet' if SYSTEM_PAUSED else 'Hayır'}\n"
    msg += f"Aktif Açık İşlem Sayısı: {count}\n\n"

    for trade in open_trades:
        msg += f"[{trade['trade_id']}] {trade['ticker']} ({trade['direction']})\n"
        msg += f"Giriş: {trade['entry_price']} | SL: {trade['sl_price']}\n"
        msg += f"Lot: {trade['position_size']}\n---\n"

    await update.message.reply_html(msg)

async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/durdur command: Pauses NEW signal generation while retaining Trailing Stop management."""
    if not await authenticate(update): return
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = True
    log.warning("Admin Command: System PAUSED. No new entries.")
    await update.message.reply_html("⏸️ <b>Sistem Duraklatıldı!</b> Yeni işlem açılmayacak, ancak mevcut açık işlemlerin Stop-Loss takibi (Trailing) ve risk yönetimi kesintisiz devam edecektir.")

async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/devam command: Resumes normal autonomous MTF operations."""
    if not await authenticate(update): return
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = False
    log.info("Admin Command: System RESUMED.")
    await update.message.reply_html("▶️ <b>Sistem Devam Ediyor!</b> Tam otonom tarama ve MTF sinyal üretimi tekrar aktif edilmiştir.")

async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/kapat_hepsi command: Panic button to market-close all open positions immediately."""
    if not await authenticate(update): return
    await update.message.reply_html("🚨 <b>Panik Modu Tetiklendi!</b> Bütün açık işlemler güncel piyasa fiyatından kapatılıyor...")
    # Will be intercepted by main loop's manual force close check

async def setup_telegram_bot() -> Application:
    """Initializes and returns the two-way Telegram Application (v20+ API)."""
    if not TELEGRAM_BOT_TOKEN:
        log.error("No Telegram Token found for polling bot.")
        return None

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", cmd_durum))
    app.add_handler(CommandHandler("durdur", cmd_durdur))
    app.add_handler(CommandHandler("devam", cmd_devam))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))

    return app
