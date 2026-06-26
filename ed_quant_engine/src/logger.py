from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request
from logging.handlers import RotatingFileHandler

from src.paths import LOG_PATH, ensure_runtime_dirs


ensure_runtime_dirs()

logger = logging.getLogger("ED_Quant_Engine")
logger.setLevel(logging.INFO)
logger.propagate = False

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class TelegramCriticalHandler(logging.Handler):
    """Best-effort CRITICAL alert without importing notifier or blocking startup."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.levelno < logging.CRITICAL:
            return
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = (os.getenv("ADMIN_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        if not token or not chat_id:
            return
        try:
            text = self.format(record)
            payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:3500]})
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            req = urllib.request.Request(
                url,
                data=payload.encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            self.handleError(record)


if not logger.handlers:
    fh = RotatingFileHandler(
        LOG_PATH,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)

    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    th = TelegramCriticalHandler()
    th.setLevel(logging.CRITICAL)
    th.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.addHandler(th)

def get_logger():
    return logger
