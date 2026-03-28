"""
ED Capital Quant Engine - Telegram Notifier
Two-way asynchronous Telegram integration.
"""
import requests
import json
import logging

try:
    from .config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
except ImportError:
    TELEGRAM_BOT_TOKEN = None
    ADMIN_CHAT_ID = None

def notify_admin(message: str) -> bool:
    """Send a message to the admin via Telegram Bot API."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        logging.warning("Telegram configuration missing. Cannot send notification.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=10)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to send Telegram message: {e}")
        return False

def process_admin_command(command: str):
    """Placeholder for processing incoming admin commands via webhook/polling."""
    pass
