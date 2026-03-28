import time
import requests
import json
from src.core.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from src.core.logger import logger
import threading

class TelegramNotifier:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = ADMIN_CHAT_ID
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/"

        # Async polling state
        self.is_polling = False
        self.last_update_id = 0
        self._commands = {}

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials missing in .env")
            return False

        url = self.api_url + "sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info("Telegram message sent successfully.")
                return True
            else:
                logger.error(f"Telegram send failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram connection error: {e}")
            return False

    def register_command(self, command: str, callback: callable):
        """Registers a command function."""
        self._commands[command] = callback

    def _poll_updates(self):
        """Long-polling for updates."""
        while self.is_polling:
            url = self.api_url + "getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 30}

            try:
                response = requests.get(url, params=params, timeout=35)
                if response.status_code == 200:
                    data = response.json()

                    if "result" in data:
                        for update in data["result"]:
                            self.last_update_id = update["update_id"]

                            if "message" in update and "text" in update["message"]:
                                msg = update["message"]
                                chat_id = str(msg["chat"]["id"])
                                text = msg["text"].strip()

                                # Strict Security: Only admin can send commands
                                if chat_id != str(self.chat_id):
                                    logger.critical(f"Unauthorized Access Attempt by Chat ID {chat_id}")
                                    continue

                                # Route commands
                                for cmd, callback in self._commands.items():
                                    if text.startswith(cmd):
                                        logger.info(f"Admin command received: {text}")
                                        try:
                                            callback(text)
                                        except Exception as e:
                                            logger.error(f"Command execution error: {e}")
            except requests.exceptions.Timeout:
                pass # Expected for long-polling
            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(5) # Backoff

    def start_polling(self):
        """Starts listening in a background thread."""
        if not self.is_polling:
            self.is_polling = True
            thread = threading.Thread(target=self._poll_updates, daemon=True)
            thread.start()
            logger.info("Telegram Polling started.")

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """Sends a document (like the Tear Sheet HTML/PDF) to Telegram."""
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram credentials missing in .env")
            return False

        url = self.api_url + "sendDocument"
        payload = {"chat_id": self.chat_id, "caption": caption}

        try:
            with open(file_path, 'rb') as f:
                files = {"document": f}
                response = requests.post(url, data=payload, files=files, timeout=30)

            if response.status_code == 200:
                logger.info(f"Telegram document ({file_path}) sent successfully.")
                return True
            else:
                logger.error(f"Telegram document send failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Telegram connection error sending document: {e}")
            return False
