import asyncio
import schedule
import time
from datetime import datetime
from live_trader import LiveTrader
from notifier import notifier
from logger import log
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID

trader = LiveTrader()

# --- TELEGRAM BOT COMMAND HANDLERS ---
async def auth_check(update: Update) -> bool:
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        log.critical(f"Unauthorized access attempt from ID: {update.effective_chat.id}")
        await update.message.reply_text("Yetkisiz erişim.")
        return False
    return True

async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    bal = trader.broker.get_account_balance()
    opens = len(trader.broker.get_open_positions())
    await update.message.reply_text(f"📊 <b>DURUM RAPORU</b>\nKasa: ${bal:.2f}\nAçık Pozisyonlar: {opens}", parse_mode="HTML")

async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    trader.is_paused = True
    await update.message.reply_text("⏸ Sistem duraklatıldı. Yeni tarama yapılmayacak (Açık pozisyon takibi aktif).")

async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    trader.is_paused = False
    await update.message.reply_text("▶ Sistem yeniden aktif edildi.")

async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    opens = trader.broker.get_open_positions()
    count = 0
    for trade in opens:
        # Simplistic market close (using DB entry price as a placeholder for current market if not fetched)
        # Real implementation would fetch current bid/ask
        trader.broker.close_position(trade['trade_id'], trade['entry_price'], "PANIC CLOSE")
        count += 1
    await update.message.reply_text(f"🚨 PANİK KAPATMASI YAPILDI: {count} pozisyon kapatıldı.")

async def cmd_tara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    await update.message.reply_text("🔍 Manuel tarama başlatılıyor...")
    # Wrap in task to not block Telegram event loop
    asyncio.create_task(trader.run_live_cycle())

# --- SCHEDULING ---
def scheduled_job():
    log.info("Scheduled task triggered.")
    asyncio.create_task(trader.run_live_cycle())

def scheduled_heartbeat():
    msg = f"🟢 <b>Sistem Aktif</b>\nZaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    notifier.send_message(msg)

async def main():
    log.info("Initializing ED Capital Quant Engine...")

    # 1. Start Telegram Bot Async
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("durum", cmd_durum))
    application.add_handler(CommandHandler("durdur", cmd_durdur))
    application.add_handler(CommandHandler("devam", cmd_devam))
    application.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
    application.add_handler(CommandHandler("tara", cmd_tara))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    log.info("Telegram interface listening...")
    notifier.send_message("🚀 <b>ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.</b>")

    # 2. Setup Scheduler
    # Run cycle every hour exactly at minute 01 (Candle Close Sync)
    schedule.every().hour.at(":01").do(scheduled_job)

    # Heartbeat daily at 08:00
    schedule.every().day.at("08:00").do(scheduled_heartbeat)

    # 3. Main Event Loop
    try:
        while True:
            schedule.run_pending()
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
