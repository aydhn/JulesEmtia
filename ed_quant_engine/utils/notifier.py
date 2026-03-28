import requests
import asyncio
from typing import Optional
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config

logger = setup_logger("Notifier")

class TelegramNotifier:
    def __init__(self, token=Config.TELEGRAM_BOT_TOKEN, chat_id=Config.ADMIN_CHAT_ID):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.token}/"
        self.last_update_id = None
        self.command_queue = asyncio.Queue()

    def send_message(self, text: str, parse_mode="HTML") -> bool:
        """Sends a one-way notification to the Admin (Phase 2)."""
        if not self.token or not self.chat_id:
             logger.warning("Telegram token/chat_id missing. Notification skipped.")
             return False

        try:
            url = f"{self.api_url}sendMessage"
            payload = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_document(self, file_path: str, caption: str = "") -> bool:
        """Sends PDF/HTML tear sheets to Telegram."""
        if not self.token or not self.chat_id:
             return False
        try:
            url = f"{self.api_url}sendDocument"
            with open(file_path, "rb") as f:
                 files = {"document": f}
                 payload = {"chat_id": self.chat_id, "caption": caption}
                 response = requests.post(url, data=payload, files=files, timeout=10)
                 response.raise_for_status()
                 return True
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    async def poll_commands_async(self):
        """Two-Way Communication (Long-Polling) for Admin Commands (Phase 17)."""
        if not self.token or not self.chat_id:
             logger.warning("Polling disabled due to missing credentials.")
             return

        logger.info("Started Telegram Command Polling (Two-Way Communication)")
        url = f"{self.api_url}getUpdates"

        while True:
            try:
                params = {"timeout": 10, "allowed_updates": ["message"]}
                if self.last_update_id:
                    params["offset"] = self.last_update_id + 1

                response = requests.get(url, params=params, timeout=15)
                data = response.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        self.last_update_id = update["update_id"]
                        msg = update.get("message", {})

                        # Strict Whitelist Authentication
                        if str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                            logger.critical(f"UNAUTHORIZED ACCESS ATTEMPT from ID: {msg.get('chat', {}).get('id')}")
                            continue

                        text = msg.get("text", "")
                        if text.startswith("/"):
                            logger.info(f"Received Admin Command: {text}")
                            await self.command_queue.put(text)

            except Exception as e:
                # Polling errors shouldn't crash the bot
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(1)
