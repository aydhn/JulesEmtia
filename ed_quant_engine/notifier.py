import os
import requests
import time
from typing import Dict, Any
from ed_quant_engine.logger import log
from ed_quant_engine.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID

def send_telegram_message(message: str, retries: int = 3, backoff: int = 60) -> bool:
    """Sends a message to the configured Telegram Admin ID using exponential backoff."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        log.warning("Telegram credentials missing. Skipping notification.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                log.info("Telegram notification sent successfully.")
                return True
            else:
                log.error(f"Telegram API Error: {response.text}")
        except Exception as e:
            log.error(f"Failed to send Telegram message (Attempt {attempt+1}/{retries}): {e}")

        time.sleep(backoff * (2 ** attempt)) # Exponential backoff: 60, 120, 240

    log.error("Telegram notification completely failed after all retries.")
    return False

def send_trade_alert(trade_data: Dict[str, Any]) -> None:
    """Formats and sends a trade opening alert."""
    msg = (
        f"🚨 <b>YENİ İŞLEM SİNYALİ</b> 🚨\n\n"
        f"<b>Varlık:</b> {trade_data['ticker']}\n"
        f"<b>Yön:</b> {'🟩 LONG' if trade_data['direction'] == 'Long' else '🟥 SHORT'}\n"
        f"<b>Giriş Fiyatı:</b> {trade_data['entry_price']:.4f}\n"
        f"<b>Stop Loss:</b> {trade_data['sl_price']:.4f}\n"
        f"<b>Take Profit:</b> {trade_data['tp_price']:.4f}\n"
        f"<b>Önerilen Pozisyon:</b> {trade_data['position_size']:.2f}%\n"
        f"\n<i>ED Capital Quant Engine</i>"
    )
    send_telegram_message(msg)

def send_critical_alert(message: str) -> None:
    """Send high priority alert for crashes or black swan events."""
    msg = f"‼️ <b>KRİTİK SİSTEM UYARISI</b> ‼️\n\n{message}"
    send_telegram_message(msg)

def send_heartbeat(cycles: int, errors: int, open_trades: int) -> None:
    msg = (
        f"🟢 <b>Sistem Aktif</b>\n\n"
        f"Son 24 saatte:\n"
        f"🔄 {cycles} Döngü Tamamlandı\n"
        f"⚠️ {errors} API Hatası Tolere Edildi\n"
        f"📈 {open_trades} Adet Açık Pozisyon Takip Ediliyor"
    )
    send_telegram_message(msg)
