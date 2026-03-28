import requests
import json
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from logger import get_logger

log = get_logger()

class TelegramNotifier:
    """
    Two-way Telegram Communication logic.
    Provides admin control commands (/durum, /durdur, /devam, /tara, /kapat_hepsi)
    and robust notifications.
    """

    def __init__(self, token=TELEGRAM_BOT_TOKEN, admin_id=ADMIN_CHAT_ID):
        self.token = token
        self.admin_id = str(admin_id)
        self.url = f"https://api.telegram.org/bot{self.token}/"

    def send_message(self, text: str):
        if not self.token or not self.admin_id:
            log.warning(f"Telegram Config Missing. Message: {text}")
            return False

        payload = {
            "chat_id": self.admin_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            r = requests.post(f"{self.url}sendMessage", json=payload, timeout=5)
            r.raise_for_status()
            log.info("Telegram message sent successfully.")
            return True
        except Exception as e:
            log.error(f"Failed to send Telegram message: {e}")
            return False

    def send_report(self, filepath: str):
        if not self.token or not self.admin_id:
            return False

        try:
            with open(filepath, "rb") as f:
                payload = {"chat_id": self.admin_id}
                files = {"document": f}
                r = requests.post(f"{self.url}sendDocument", data=payload, files=files, timeout=30)
                r.raise_for_status()
            log.info(f"Report {filepath} sent via Telegram.")
            return True
        except Exception as e:
            log.error(f"Failed to send Telegram report: {e}")
            return False
