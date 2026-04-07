import requests
import os
import time
from typing import Optional
from .logger import quant_logger

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("ADMIN_CHAT_ID")

    def send_message(self, message: str, retry_count: int = 3) -> bool:
        if not self.bot_token or not self.chat_id:
            quant_logger.warning("Telegram credentials not found. Message not sent.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}

        for attempt in range(retry_count):
            try:
                response = requests.post(url, json=payload, timeout=10)
                if response.status_code == 200:
                    return True
                else:
                    quant_logger.warning(f"Telegram API error {response.status_code}: {response.text}")
            except Exception as e:
                quant_logger.warning(f"Telegram request failed (Attempt {attempt+1}/{retry_count}): {e}")

            # Exponential backoff
            time.sleep(2 ** attempt)

        quant_logger.error("Failed to send Telegram message after max retries.")
        return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        if not self.bot_token or not self.chat_id:
            return False

        if not os.path.exists(file_path):
            quant_logger.error(f"File not found for Telegram upload: {file_path}")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                response = requests.post(url, data={"chat_id": self.chat_id, "caption": caption}, files={"document": f}, timeout=30)
            if response.status_code == 200:
                quant_logger.info(f"File sent successfully: {file_path}")
                return True
            else:
                quant_logger.error(f"Telegram file upload failed: {response.text}")
        except Exception as e:
            quant_logger.error(f"Telegram file upload exception: {e}")
        return False
