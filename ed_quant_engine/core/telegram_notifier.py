import requests
from core.config import TELEGRAM_TOKEN, ADMIN_CHAT_ID
from core.logger import get_logger

log = get_logger()

def send_message(msg: str):
    if TELEGRAM_TOKEN == "dummy_token" or ADMIN_CHAT_ID == "dummy_id":
        log.warning(f"Telegram Config Missing. Msg: {msg}")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": ADMIN_CHAT_ID, "text": msg}
    try:
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code != 200:
            log.error(f"Telegram API Error: {r.text}")
    except Exception as e:
        log.error(f"Telegram Connection Error: {e}")
