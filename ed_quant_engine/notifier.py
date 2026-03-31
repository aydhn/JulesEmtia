import requests
import os
import asyncio
from dotenv import load_dotenv
from logger import logger

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

def send_telegram_message(message: str) -> None:
    """
    Synchronous fallback for sending Telegram messages using requests.
    Zero-budget, lightweight notification pipeline.
    """
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.warning("Telegram credentials missing. Message not sent.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")

async def async_send_telegram_message(message: str) -> None:
    """
    Asynchronous version to avoid blocking the main event loop.
    Uses asyncio.to_thread for the blocking requests call.
    """
    await asyncio.to_thread(send_telegram_message, message)

