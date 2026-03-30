import os
import requests
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from .config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from .logger import log_info, log_error, log_warning
from .paper_db import get_account_balance, get_open_trades
from .reporter import generate_tear_sheet

def send_telegram_message(message: str):
    """
    Sıfır Maliyetli / Standart Telegram Bildirimi (Senkron).
    Acil durumlar ve tek yönlü bildirimler için.
    """
    if TELEGRAM_TOKEN == "your_token_here" or not TELEGRAM_TOKEN:
        log_warning("Telegram Token yok, mesaj konsola basılıyor: " + message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code != 200:
            log_error(f"Telegram Gönderim Hatası: {response.text}")
    except Exception as e:
        log_error(f"Telegram Bağlantı Hatası: {e}")

async def send_document(file_path: str, caption: str = ""):
    """
    Tear Sheet / Rapor dosyasını PDF veya HTML olarak asenkron gönderir.
    """
    if not os.path.exists(file_path) or TELEGRAM_TOKEN == "your_token_here":
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": ADMIN_CHAT_ID, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=30)
            if response.status_code != 200:
                log_error(f"Belge Gönderim Hatası: {response.text}")
    except Exception as e:
        log_error(f"Belge Gönderim Bağlantı Hatası: {e}")

# --- ÇİFT YÖNLÜ İLETİŞİM (Two-Way Communication) ---
# Global State Kontrolü için main.py tarafından dinlenecek değişkenler
SYSTEM_PAUSED = False
FORCE_SCAN = False
PANIC_CLOSE = False

async def _check_auth(update: Update) -> bool:
    """Yalnızca ADMIN_CHAT_ID ile komutları kabul et (Katı Güvenlik)."""
    user_id = str(update.effective_chat.id)
    if user_id != str(ADMIN_CHAT_ID):
        log_critical(f"YETKİSİZ ERİŞİM DENEMESİ! ID: {user_id}")
        return False
    return True

async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update): return
    balance = get_account_balance()
    trades = get_open_trades()

    msg = f"📊 <b>GÜNCEL DURUM</b>\n\n"
    msg += f"Kasa: <b>${balance:,.2f}</b>\n"
    msg += f"Açık Pozisyon: {len(trades)}\n"
    msg += f"Sistem Duraklatıldı: {'Evet 🔴' if SYSTEM_PAUSED else 'Hayır 🟢'}\n\n"

    for t in trades:
        msg += f"• <b>{t['ticker']}</b> | {t['direction']} | Giriş: {t['entry_price']:.4f}\n"

    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SYSTEM_PAUSED
    if not await _check_auth(update): return
    SYSTEM_PAUSED = True
    msg = "🔴 <b>SİSTEM DURDURULDU!</b>\nYeni sinyal taraması askıya alındı. Açık pozisyonların koruması (İzleyen Stop vb.) DEVAM EDİYOR."
    log_warning("Kullanıcı müdahalesi: Sistem duraklatıldı.")
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global SYSTEM_PAUSED
    if not await _check_auth(update): return
    SYSTEM_PAUSED = False
    msg = "🟢 <b>SİSTEM DEVAM EDİYOR!</b>\nOtonom tarama modu tekrar aktifleştirildi."
    log_info("Kullanıcı müdahalesi: Sistem devam ediyor.")
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global PANIC_CLOSE
    if not await _check_auth(update): return
    PANIC_CLOSE = True
    msg = "🚨 <b>PANİK BUTONU!</b>\nTüm açık pozisyonlar acilen kapatılıyor..."
    log_critical("Kullanıcı müdahalesi: PANİK KAPATMASI (Kapat Hepsi) tetiklendi!")
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_tara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global FORCE_SCAN
    if not await _check_auth(update): return
    FORCE_SCAN = True
    msg = "🔎 <b>ANLIK TARAMA İSTENDİ!</b>\nZamanlayıcı beklenmeden tüm evren şimdi taranıyor..."
    log_info("Kullanıcı müdahalesi: Anlık tarama tetiklendi.")
    await update.message.reply_text(msg, parse_mode="HTML")

async def cmd_rapor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_auth(update): return
    msg = "📄 Kurumsal Performans Raporu (Tear Sheet) hazırlanıyor, lütfen bekleyin..."
    await update.message.reply_text(msg)

    file_path = generate_tear_sheet()
    if file_path:
        await send_document(file_path, caption="ED Capital Yönetim Raporu")
    else:
        await update.message.reply_text("Rapor oluşturulamadı. Yeterli kapalı işlem olmayabilir.")

def start_telegram_listener():
    """
    python-telegram-bot (v20+) ile çift yönlü dinleme servisini başlatır.
    Senkron çağrıdır, kendi asyncio event loop'unu kurar, ancak biz bunu main.py
    içinde arka planda çalıştıracağız (Application builder).
    """
    if TELEGRAM_TOKEN == "your_token_here":
        return None

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("durum", cmd_durum))
    app.add_handler(CommandHandler("durdur", cmd_durdur))
    app.add_handler(CommandHandler("devam", cmd_devam))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
    app.add_handler(CommandHandler("tara", cmd_tara))
    app.add_handler(CommandHandler("rapor", cmd_rapor))

    return app
