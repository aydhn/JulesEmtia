import requests
import asyncio
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from logger import log

class TelegramNotifier:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN, chat_id: str = ADMIN_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        if not self.token or not self.chat_id:
            log.warning("Telegram credentials not found. Message not sent.")
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            # Synchronous request for simple logging
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                log.info(f"Telegram message sent successfully.")
                return True
            else:
                log.error(f"Failed to send Telegram message. Status: {response.status_code}, Response: {response.text}")
                return False
        except Exception as e:
            log.error(f"Exception during Telegram send_message: {e}")
            return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        if not self.token or not self.chat_id:
            return False

        url = f"{self.base_url}/sendDocument"
        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': self.chat_id, 'caption': caption}
                response = requests.post(url, files=files, data=data, timeout=30)

            if response.status_code == 200:
                log.info(f"Telegram document {file_path} sent successfully.")
                return True
            else:
                log.error(f"Failed to send Telegram document. Status: {response.status_code}")
                return False
        except Exception as e:
            log.error(f"Exception during Telegram send_document: {e}")
            return False

# Global instance
notifier = TelegramNotifier()
