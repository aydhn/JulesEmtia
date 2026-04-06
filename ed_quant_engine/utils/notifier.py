import os
import asyncio
import requests
from typing import Optional
from utils.logger import setup_logger

logger = setup_logger("Notifier")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

async def send_telegram_message(message: str) -> None:
    """Sends a professional, asynchronous Telegram notification directly via API."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Telegram Bot Token veya Chat ID bulunamadı. Bildirim gönderilemiyor.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        # Asynchronously make the HTTP request using asyncio.to_thread
        response = await asyncio.to_thread(requests.post, url, json=payload, timeout=10)

        if response.status_code != 200:
            logger.error(f"Telegram mesajı iletilemedi: {response.text}")
        else:
            logger.info("Telegram bildirimi başarıyla gönderildi.")
    except Exception as e:
        logger.error(f"Telegram ağ hatası (Retry tetiklenmeli): {str(e)}")

async def send_telegram_document(file_path: str, caption: str = "") -> None:
    """Sends a document (PDF, HTML tear sheet) via Telegram."""
    if not BOT_TOKEN or not ADMIN_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    try:
        with open(file_path, 'rb') as f:
            files = {'document': f}
            data = {'chat_id': ADMIN_CHAT_ID, 'caption': caption}
            response = await asyncio.to_thread(requests.post, url, files=files, data=data, timeout=30)
            if response.status_code == 200:
                logger.info(f"Rapor dosyası başarıyla iletildi: {file_path}")
            else:
                logger.error(f"Dosya gönderme hatası: {response.text}")
    except Exception as e:
        logger.error(f"Dosya okuma/gönderme kritik hatası: {str(e)}")
