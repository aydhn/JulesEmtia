import re

with open("ed_quant_engine/src/notifier.py", "r") as f:
    content = f.read()

new_send_message = """
    async def send_message(self, text: str):
        if not self.token or self.token == "DUMMY_TOKEN" or not self.admin_id:
            logger.warning(f"Telegram not configured. Logged msg: {text}")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.admin_id, "text": text, "parse_mode": "Markdown"}
        for attempt in range(3):
            try:
                await asyncio.to_thread(requests.post, url, json=payload, timeout=5)
                break
            except Exception as e:
                sleep_time = 1 * (2 ** attempt)
                logger.error(f"Telegram send failed (Attempt {attempt+1}): {e}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        else:
             logger.error("Failed to send Telegram message after 3 attempts.")
"""

old_send_message_pattern = r"    async def send_message\(self, text: str\):.*?except Exception as e:\n            logger\.error\(f\"Telegram send failed: \{e\}\"\)"

content = re.sub(old_send_message_pattern, new_send_message.strip(), content, flags=re.DOTALL)


new_send_document = """
    async def send_document(self, doc_path: str, caption: str = ""):
        if not self.token or self.token == "DUMMY_TOKEN" or not self.admin_id: return
        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        for attempt in range(3):
            try:
                with open(doc_path, 'rb') as doc:
                    payload = {"chat_id": self.admin_id, "caption": caption}
                    files = {"document": doc}
                    await asyncio.to_thread(requests.post, url, data=payload, files=files, timeout=10)
                break
            except Exception as e:
                sleep_time = 1 * (2 ** attempt)
                logger.error(f"Telegram doc send failed (Attempt {attempt+1}): {e}. Retrying in {sleep_time}s...")
                await asyncio.sleep(sleep_time)
        else:
            logger.error("Failed to send Telegram document after 3 attempts.")
"""

old_send_document_pattern = r"    async def send_document\(self, doc_path: str, caption: str = \"\"\):.*?except Exception as e:\n            logger\.error\(f\"Telegram doc send failed: \{e\}\"\)"

content = re.sub(old_send_document_pattern, new_send_document.strip(), content, flags=re.DOTALL)


with open("ed_quant_engine/src/notifier.py", "w") as f:
    f.write(content)
