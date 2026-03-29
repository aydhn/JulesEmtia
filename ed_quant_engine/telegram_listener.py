import os
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from ed_quant_engine.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from ed_quant_engine.logger import log

class BotController:
    """Manages bot state across threads."""
    def __init__(self):
        self.is_paused = False
        self.force_scan = False
        self.panic_close = False

bot_controller = BotController()

async def verify_user(update: Update) -> bool:
    """Check if the sender is the authorized admin."""
    chat_id = str(update.effective_chat.id)
    if chat_id != str(ADMIN_CHAT_ID):
        log.critical(f"Unauthorized Telegram access attempt from ID: {chat_id}")
        await update.message.reply_text("Yetkisiz Erişim! Loglandı.")
        return False
    return True

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_user(update): return
    from ed_quant_engine.paper_db import get_open_trades
    open_trades = get_open_trades()

    msg = f"📊 <b>DURUM RAPORU</b>\n\n"
    msg += f"Aktif Pozisyonlar: {len(open_trades)}\n"
    msg += f"Sistem Durumu: {'⏸️ DURAKLATILDI' if bot_controller.is_paused else '▶️ ÇALIŞIYOR'}\n\n"

    for t in open_trades:
        msg += f"{t['ticker']} {t['direction']} Giriş: {t['entry_price']}\n"

    await update.message.reply_html(msg)

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_user(update): return
    bot_controller.is_paused = True
    await update.message.reply_html("⏸️ <b>Sistem Duraklatıldı.</b> Yeni sinyal aranmıyor. Açık pozisyon takibi devam ediyor.")
    log.info("System manually paused via Telegram.")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_user(update): return
    bot_controller.is_paused = False
    await update.message.reply_html("▶️ <b>Sistem Devam Ediyor.</b> Otonom tarama aktif.")
    log.info("System manually resumed via Telegram.")

async def panic_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_user(update): return
    bot_controller.panic_close = True
    await update.message.reply_html("🚨 <b>PANİK BUTONUNA BASILDI!</b> Tüm açık pozisyonlar acilen kapatılıyor.")
    log.critical("Panic close triggered via Telegram.")

async def force_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await verify_user(update): return
    bot_controller.force_scan = True
    await update.message.reply_html("🔍 <b>TARAMA ZORLANIYOR.</b> Zamanlayıcı beklenmeden tarama başlatılıyor.")
    log.info("Force scan triggered via Telegram.")

def start_telegram_listener():
    """Starts the long-polling Telegram listener in a non-blocking thread."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("Telegram credentials missing. Listener not starting.")
        return

    def run_polling():
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("durum", status_command))
        app.add_handler(CommandHandler("durdur", pause_command))
        app.add_handler(CommandHandler("devam", resume_command))
        app.add_handler(CommandHandler("kapat_hepsi", panic_command))
        app.add_handler(CommandHandler("tara", force_scan_command))
        log.info("Telegram listener started successfully in background thread.")
        app.run_polling(drop_pending_updates=True)

    thread = threading.Thread(target=run_polling, daemon=True)
    thread.start()

if __name__ == "__main__":
    start_telegram_listener()
    import time
    while True: time.sleep(1)
