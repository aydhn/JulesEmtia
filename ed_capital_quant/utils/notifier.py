import os
import asyncio
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from utils.logger import log
from core.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID

TOKEN = TELEGRAM_BOT_TOKEN
ADMIN_ID = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID and ADMIN_CHAT_ID.isdigit() else 0
bot = Bot(token=TOKEN) if TOKEN else None

STATE = {"paused": False, "force_scan": False, "panic_close": False}

async def send_msg(text: str):
    if not bot:
        log.warning("Telegram Bot Token eksik, mesaj gönderilemedi: " + text)
        return
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode='HTML')
    except Exception as e:
        log.error(f"Telegram Hatası: {e}")

async def check_admin(update: Update) -> bool:
    if update.effective_user.id != ADMIN_ID:
        log.critical(f"Yetkisiz Erişim Denemesi: {update.effective_user.id}")
        await update.message.reply_text("Yetkisiz işlem.")
        return False
    return True

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    status_str = "DURAKLATILDI" if STATE["paused"] else "AKTİF"
    await update.message.reply_text(f"🟢 Sistem Durumu: {status_str}\nAnaliz döngüsü devam ediyor.")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    STATE["paused"] = True
    await update.message.reply_text("⏸ Sistem duraklatıldı. Açık pozisyonlar izlenmeye devam edecek, ancak yeni sinyal aranmayacak.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    STATE["paused"] = False
    await update.message.reply_text("▶️ Sistem yeniden başlatıldı. Tam otonom tarama aktif.")

async def cmd_panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    STATE["panic_close"] = True
    await update.message.reply_text("🚨 PANİK MODU: Tüm açık pozisyonlar acilen piyasa fiyatından kapatılacak!")

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update): return
    STATE["force_scan"] = True
    await update.message.reply_text("🔍 Zorunlu tarama başlatılıyor. Zamanlayıcı beklenmeden tüm evren taranacak.")

async def start_polling():
    if not TOKEN:
        log.warning("Telegram Bot Token eksik, dinleme başlatılamadı.")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("durum", cmd_status))
    app.add_handler(CommandHandler("durdur", cmd_pause))
    app.add_handler(CommandHandler("devam", cmd_resume))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_panic))
    app.add_handler(CommandHandler("tara", cmd_scan))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()
