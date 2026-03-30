import os
import asyncio
import traceback
import requests
from dotenv import load_dotenv
from typing import Optional

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from src.logger import get_logger

load_dotenv()
logger = get_logger("notifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID")

# Global State Flags for Commands
global_state = {
    "is_paused": False,
    "force_scan": False
}

def is_admin(update: Update) -> bool:
    """Security check to ensure only the admin can run commands."""
    user_id = str(update.message.chat_id)
    if user_id != ADMIN_CHAT_ID:
        logger.critical(f"Unauthorized access attempt by ID: {user_id}")
        return False
    return True

async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    from src.broker import PaperBroker
    broker = PaperBroker()
    bal = broker.get_account_balance()
    open_pos = broker.get_open_positions()
    msg = f"📊 <b>Durum Raporu</b>\n\n<b>Bakiye:</b> ${bal:,.2f}\n<b>Açık Pozisyon:</b> {len(open_pos)}\n<b>Duraklatıldı:</b> {'Evet' if global_state['is_paused'] else 'Hayır'}"
    await update.message.reply_html(msg)

async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global_state["is_paused"] = True
    await update.message.reply_html("⏸️ <b>Sistem Durduruldu.</b> Yeni pozisyon açılmayacak, ancak açık pozisyonlar (Trailing Stop vb.) takip edilmeye devam edecek.")

async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global_state["is_paused"] = False
    await update.message.reply_html("▶️ <b>Sistem Devam Ediyor.</b> Tam otonom tarama modu aktif.")

async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    from src.broker import PaperBroker
    from src.execution_model import apply_execution_costs
    import yfinance as yf

    broker = PaperBroker()
    open_pos = broker.get_open_positions()

    if not open_pos:
        await update.message.reply_html("Kapatılacak açık pozisyon yok.")
        return

    await update.message.reply_html("🚨 <b>Panik Modu:</b> Tüm pozisyonlar piyasa fiyatından kapatılıyor...")

    closed_count = 0
    for p in open_pos:
        ticker = p['ticker']
        try:
            curr_price = yf.download(ticker, period="1d", interval="1m", progress=False)['Close'].iloc[-1]
            exit_price = apply_execution_costs(ticker, "Close", curr_price, 0.0, 0.0)

            pnl = (exit_price - p['entry_price']) * p['position_size'] if p['direction'] == "Long" else (p['entry_price'] - exit_price) * p['position_size']
            broker.close_position(p['trade_id'], exit_price, pnl, "Panic Close")
            closed_count += 1
        except Exception as e:
            logger.error(f"Failed to panic close {ticker}: {e}")

    await update.message.reply_html(f"✅ <b>İşlem Tamamlandı.</b> {closed_count} adet pozisyon kapatıldı.")

async def cmd_tara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global_state["force_scan"] = True
    await update.message.reply_html("🔍 <b>Zorunlu Tarama (Force Scan) tetiklendi.</b> Bir sonraki döngüde tarama derhal başlatılacak.")

async def start_telegram_listener():
    """Starts the python-telegram-bot application in non-blocking mode."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Telegram credentials missing. Listener not started.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("durum", cmd_durum))
    app.add_handler(CommandHandler("durdur", cmd_durdur))
    app.add_handler(CommandHandler("devam", cmd_devam))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
    app.add_handler(CommandHandler("tara", cmd_tara))

    logger.info("Starting Telegram Command Listener...")

    # Initialize and start the application gracefully without blocking the main event loop
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

# ---------------------------------------------------------
# Outbound Message Methods
# ---------------------------------------------------------

def send_telegram_message_sync(message: str) -> bool:
    """Synchronous Telegram message dispatch."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return False
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_CHAT_ID, "text": message, "parse_mode": "HTML"}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send sync Telegram message: {e}")
        return False

async def send_telegram_message_async(message: str) -> bool:
    return await asyncio.to_thread(send_telegram_message_sync, message)

async def send_telegram_document_async(file_path: str, caption: str = "") -> bool:
    if not BOT_TOKEN or not ADMIN_CHAT_ID: return False
    def _send_doc():
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": ADMIN_CHAT_ID, "caption": caption}
                response = requests.post(url, files=files, data=data, timeout=30)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False
    return await asyncio.to_thread(_send_doc)

def notify_critical_error(e: Exception, context: str = ""):
    tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
    msg = f"🚨 <b>CRITICAL ERROR</b> 🚨\n\n<b>Context:</b> {context}\n<b>Exception:</b> {str(e)}\n\n<pre>{tb[-500:]}</pre>"
    logger.critical(f"Critical error in {context}: {e}")
    send_telegram_message_sync(msg)
