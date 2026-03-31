import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from paper_broker import PaperBroker
from logger import setup_logger

logger = setup_logger("TelegramInterface")
broker = PaperBroker()

ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
system_paused = False

def check_admin(update: Update) -> bool:
    """Security verification for incoming commands."""
    user_id = str(update.effective_chat.id)
    if user_id != ADMIN_CHAT_ID:
        logger.critical(f"YETKİSİZ ERİŞİM DENEMESİ! User ID: {user_id}")
        return False
    return True

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Returns current portfolio status, open positions, and daily PnL."""
    if not check_admin(update): return

    balance = broker.get_account_balance()
    positions = broker.get_open_positions()

    msg = f"🟢 <b>Sistem Durumu</b>\n\n"
    msg += f"Güncel Bakiye: ${balance:,.2f}\n"
    msg += f"Duraklatıldı (Paused): {'Evet' if system_paused else 'Hayır'}\n\n"

    msg += f"<b>Açık Pozisyonlar ({len(positions)}):</b>\n"
    for pos in positions:
        msg += f"- {pos['direction']} {pos['ticker']} @ {pos['entry_price']:.4f} (Lot: {pos['position_size']:.2f})\n"

    await update.message.reply_text(msg, parse_mode='HTML')

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Pauses new trade generation but keeps monitoring open trades."""
    if not check_admin(update): return
    global system_paused
    system_paused = True
    logger.info("Sistem Duraklatıldı (/durdur).")
    await update.message.reply_text("⏸ Sistem yeni sinyal aramayı durdurdu. Açık pozisyonlar izlenmeye devam ediyor.")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Resumes full autonomous operation."""
    if not check_admin(update): return
    global system_paused
    system_paused = False
    logger.info("Sistem Devam Ediyor (/devam).")
    await update.message.reply_text("▶️ Sistem otonom tarama moduna geri döndü.")

async def panic_close_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Emergency Panic Button: Closes all open positions immediately at market."""
    if not check_admin(update): return

    positions = broker.get_open_positions()
    if not positions:
        await update.message.reply_text("Panik yapılacak açık pozisyon yok.")
        return

    for pos in positions:
        # Fetch current price directly for panic close
        from data_loader import fetch_live_data
        df = await fetch_live_data(pos['ticker'], interval="5m")
        if df.empty: continue
        current_price = df['Close'].iloc[-1]

        # Calculate PnL roughly
        if pos['direction'] == 'Long':
            pnl = (current_price - pos['entry_price']) * pos['position_size']
            pct = ((current_price - pos['entry_price'])/pos['entry_price'])*100
        else:
            pnl = (pos['entry_price'] - current_price) * pos['position_size']
            pct = ((pos['entry_price'] - current_price)/pos['entry_price'])*100

        broker.close_position(str(pos['trade_id']), current_price, pnl, pct)

    logger.critical("🚨 PANİK BUTONU KULLANILDI. TÜM POZİSYONLAR KAPATILDI.")
    await update.message.reply_text("🚨 PANİK ÇIKIŞI TAMAMLANDI. Bütün pozisyonlar anlık fiyattan kapatıldı.")

async def force_scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Forces an immediate market scan, ignoring the schedule."""
    if not check_admin(update): return

    await update.message.reply_text("🔍 Zorunlu (Force) Tarama başlatılıyor... Lütfen bekleyin.")
    # Import the live trader cycle and execute it asynchronously
    from live_trader import run_live_cycle
    asyncio.create_task(run_live_cycle())

async def run_telegram_bot_task():
    """Asynchronous setup for python-telegram-bot (v20+) running within the existing event loop."""
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN eksik. Telegram dinleyicisi başlatılamadı.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("durum", status_command))
    application.add_handler(CommandHandler("durdur", pause_command))
    application.add_handler(CommandHandler("devam", resume_command))
    application.add_handler(CommandHandler("kapat_hepsi", panic_close_command))
    application.add_handler(CommandHandler("tara", force_scan_command))

    logger.info("Telegram İki Yönlü Komut Dinleyicisi Başlatıldı.")

    # Initialize and start application in existing loop
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)

# Combine this with LiveTrader in production
