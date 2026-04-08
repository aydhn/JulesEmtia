import os
import requests
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import logging
from src.config import TELEGRAM_TOKEN, ADMIN_CHAT_ID

logger = logging.getLogger(__name__)

class TelegramNotifier:
    """
    Phase 2: Notification System
    Phase 17: Two-Way Comms & Admin Commands
    """
    def __init__(self):
        self.token = TELEGRAM_TOKEN
        self.admin_id = str(ADMIN_CHAT_ID)
        self.is_paused = False
        self.app: Optional[Application] = None
        self.scan_callback = None
        self.close_all_callback = None
        self.get_status_callback = None

    def auth_check(func):
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            if str(update.message.chat_id) != self.admin_id:
                logger.critical(f"Unauthorized access attempt from ID: {update.message.chat_id}")
                return
            await func(self, update, context)
        return wrapper

    @auth_check
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        msg = "Durum bilgisi alınıyor..."
        if self.get_status_callback:
            msg = self.get_status_callback()
        await update.message.reply_text(msg)

    @auth_check
    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.is_paused = True
        await update.message.reply_text("⏸ Sistem Duraklatıldı. Yeni sinyal aranmayacak (Açık pozisyon takibi devam ediyor).")

    @auth_check
    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.is_paused = False
        await update.message.reply_text("▶️ Sistem Devam Ediyor. Otonom tarama aktif.")

    @auth_check
    async def cmd_close_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚨 PANİK BUTONU TETİKLENDİ. Tüm pozisyonlar kapatılıyor...")
        if self.close_all_callback:
            await self.close_all_callback()

    @auth_check
    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Manuel tarama (Force Scan) başlatılıyor...")
        if self.scan_callback:
            asyncio.create_task(self.scan_callback())

    async def start_polling(self, get_status_cb=None, close_all_cb=None, scan_cb=None):
        if not self.token or self.token == "DUMMY_TOKEN" or not self.admin_id:
            logger.error("Telegram Token or Admin ID missing. Polling not started.")
            return

        self.get_status_callback = get_status_cb
        self.close_all_callback = close_all_cb
        self.scan_callback = scan_cb

        self.app = Application.builder().token(self.token).build()
        self.app.add_handler(CommandHandler("durum", self.cmd_status))
        self.app.add_handler(CommandHandler("durdur", self.cmd_pause))
        self.app.add_handler(CommandHandler("devam", self.cmd_resume))
        self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_close_all))
        self.app.add_handler(CommandHandler("tara", self.cmd_scan))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def send_message(self, text: str):
        if not self.token or self.token == "DUMMY_TOKEN" or not self.admin_id:
            logger.warning(f"Telegram not configured. Logged msg: {text}")
            return
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {"chat_id": self.admin_id, "text": text, "parse_mode": "Markdown"}
        try:
            await asyncio.to_thread(requests.post, url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")

    async def send_document(self, doc_path: str, caption: str = ""):
        if not self.token or self.token == "DUMMY_TOKEN" or not self.admin_id: return
        url = f"https://api.telegram.org/bot{self.token}/sendDocument"
        try:
            with open(doc_path, 'rb') as doc:
                payload = {"chat_id": self.admin_id, "caption": caption}
                files = {"document": doc}
                await asyncio.to_thread(requests.post, url, data=payload, files=files, timeout=10)
        except Exception as e:
            logger.error(f"Telegram doc send failed: {e}")

tg_bot = TelegramNotifier()
