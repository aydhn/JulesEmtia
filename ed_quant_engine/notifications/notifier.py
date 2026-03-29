import requests
import json
import traceback
import ed_quant_engine.config as config
from ed_quant_engine.core.logger import logger

def send_telegram_message(message: str, force: bool = False):
    """
    Sends a message to the Telegram admin channel.
    Uses requests library to keep it zero-budget and lightweight.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        logger.warning("Telegram token or Chat ID is missing. Message not sent.")
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Telegram message sent: {message[:50]}...")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        logger.error(traceback.format_exc())

def send_document(file_path: str, caption: str = ""):
    """
    Sends a file (like a PDF report or HTML) to Telegram.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.ADMIN_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendDocument"
    try:
        with open(file_path, "rb") as f:
            files = {"document": f}
            data = {"chat_id": config.ADMIN_CHAT_ID, "caption": caption}
            response = requests.post(url, data=data, files=files, timeout=30)
            response.raise_for_status()
            logger.info(f"Document {file_path} sent to Telegram.")
    except Exception as e:
        logger.error(f"Failed to send document: {e}")
