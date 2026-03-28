import requests
import json
import threading
import time
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from logger import get_logger

log = get_logger()

class TelegramNotifier:
    """
    Two-way Telegram Communication logic using requests-based long polling.
    Provides admin control commands (/durum, /durdur, /devam, /tara, /kapat_hepsi)
    and robust notifications, running in a background thread to be non-blocking.
    """

    def __init__(self, token=TELEGRAM_BOT_TOKEN, admin_id=ADMIN_CHAT_ID):
        self.token = token
        self.admin_id = str(admin_id)
        self.url = f"https://api.telegram.org/bot{self.token}/"
        self.offset = 0
        self.is_running = False
        self.callbacks = {}

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

    def register_command(self, command: str, callback: callable):
        self.callbacks[command] = callback

    def _poll(self):
        while self.is_running:
            try:
                response = requests.get(f"{self.url}getUpdates", params={"offset": self.offset, "timeout": 10}, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        message = update.get("message")
                        if message and "text" in message:
                            chat_id = str(message["chat"]["id"])
                            text = message["text"].strip().lower()

                            if chat_id != self.admin_id:
                                log.critical(f"Unauthorized Telegram Access Attempt from {chat_id}: {text}")
                                continue

                            if text in self.callbacks:
                                log.info(f"Received Admin Command: {text}")
                                self.callbacks[text]()

            except Exception as e:
                time.sleep(5)
            time.sleep(1)

    def start_polling(self):
        if not self.token or not self.admin_id:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()
        log.info("Telegram Long-Polling initialized in background thread.")

    def stop_polling(self):
        self.is_running = False
