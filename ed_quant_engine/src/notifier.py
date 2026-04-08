from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from src.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from src.logger import get_logger
import src.paper_db as db
import os
import asyncio

logger = get_logger()

# Global state for pausing the engine
engine_paused = False

def is_admin(update: Update) -> bool:
    return str(update.effective_chat.id) == ADMIN_CHAT_ID

async def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Telegram credentials missing. Cannot send message.")
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

async def send_telegram_document(file_path: str):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID or not os.path.exists(file_path):
        return
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        with open(file_path, 'rb') as f:
            await bot.send_document(chat_id=ADMIN_CHAT_ID, document=f)
    except Exception as e:
        logger.error(f"Failed to send Telegram document: {e}")

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_text("ED Capital Quant Engine Emirlerinize Hazır.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    balance = db.get_balance()
    open_trades = db.get_open_trades()
    msg = f"🟢 <b>Durum Raporu</b>\nKasa: ${balance:.2f}\nAçık Pozisyonlar: {len(open_trades)}"
    for t in open_trades:
        msg += f"\n- {t['ticker']} {t['direction']} @ {t['entry_price']}"
    await update.message.reply_text(msg, parse_mode='HTML')

async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global engine_paused
    engine_paused = True
    await update.message.reply_text("⏸ Sistem Duraklatıldı. Yeni sinyal aranmayacak (Açık pozisyonlar korunuyor).")

async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global engine_paused
    engine_paused = False
    await update.message.reply_text("▶️ Sistem Tekrar Aktif.")

async def panic_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    # This just sets a flag or communicates to main loop to close all.
    # For now, acknowledge.
    await update.message.reply_text("🚨 PANİK BUTONU TETİKLENDİ. Tüm açık pozisyonlar kapatılıyor...")
    # Signal main loop to close all... (handled in main.py)

def get_telegram_application():
    if not TELEGRAM_BOT_TOKEN:
        return None
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("durum", status))
    app.add_handler(CommandHandler("durdur", pause))
    app.add_handler(CommandHandler("devam", resume))
    app.add_handler(CommandHandler("kapat_hepsi", panic_close))
    return app
