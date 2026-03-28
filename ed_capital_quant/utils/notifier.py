import os
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils.logger import log
from core.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID

TOKEN = TELEGRAM_BOT_TOKEN
ADMIN_ID = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID and ADMIN_CHAT_ID.isdigit() else 0
bot = Bot(token=TOKEN) if TOKEN else None

async def send_msg(text: str):
    if not bot:
        log.warning("Telegram Bot Token eksik, mesaj gönderilemedi: " + text)
        return
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='HTML')
    except Exception as e:
        log.error(f"Telegram Hatası: {e}")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        log.critical(f"Yetkisiz Erişim Denemesi: {update.effective_user.id}")
        return
    await update.message.reply_text("🟢 Sistem Aktif. VIX Normal. Kasa: Analiz ediliyor...")

async def start_polling():
    if not TOKEN:
        log.warning("Telegram Bot Token eksik, dinleme başlatılamadı.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("durum", cmd_status))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
