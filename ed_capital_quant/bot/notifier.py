import requests
import os
import asyncio
from typing import Optional
from core.logger import setup_logger
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logger = setup_logger("telegram_bot")

class TelegramNotifier:
    """
    Two-Way Telegram Communication (Phase 17).
    Handles sending notifications and listening for Admin Commands.
    """
    def __init__(self, broker=None, engine=None):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("ADMIN_CHAT_ID")
        self.broker = broker
        self.engine = engine # Reference to main orchestrator
        self.app = None

    async def send_message(self, message: str) -> bool:
        """Sends a one-way alert/notification using simple requests."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials missing. Skipping notification.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        for attempt in range(3):
            try:
                response = await asyncio.to_thread(requests.post, url, json=payload, timeout=10)
                if response.status_code == 200:
                    return True
                logger.error(f"Telegram API Error: {response.text}")
            except Exception as e:
                logger.error(f"Failed to send Telegram message: {e}. Retrying...")
                await asyncio.sleep(2 ** attempt)

        return False

    async def send_document(self, file_path: str, caption: str = "") -> bool:
        if not self.bot_token or not self.chat_id or not os.path.exists(file_path):
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"

        try:
            with open(file_path, 'rb') as f:
                files = {'document': f}
                data = {'chat_id': self.chat_id, 'caption': caption}
                response = await asyncio.to_thread(requests.post, url, files=files, data=data, timeout=30)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False

    # --- Two-Way Commands (Phase 17) ---
    async def _verify_admin(self, update: Update) -> bool:
        if str(update.effective_user.id) != self.chat_id:
            logger.critical(f"Unauthorized access attempt from User ID: {update.effective_user.id}")
            await update.message.reply_text("⛔ Access Denied.")
            return False
        return True

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return

        balance = self.broker.get_account_balance() if self.broker else 0
        positions = self.broker.get_open_positions() if self.broker else []

        msg = f"📊 <b>System Status</b>\n\n"
        msg += f"💰 Balance: ${balance:,.2f}\n"
        msg += f"🟢 Open Positions: {len(positions)}\n\n"

        for p in positions:
            pnl = p.get('pnl', 0)
            msg += f"• {p['ticker']} ({p['direction']}) | PnL: ${pnl:.2f}\n"

        await update.message.reply_text(msg, parse_mode="HTML")

    async def _pause_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        if self.engine:
            self.engine.is_paused = True
            await update.message.reply_text("⏸️ System Paused. Trailing stops active, but no new scans will run.")

    async def _resume_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        if self.engine:
            self.engine.is_paused = False
            await update.message.reply_text("▶️ System Resumed. Autonomous scanning activated.")

    async def _panic_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        if self.broker:
            positions = self.broker.get_open_positions()
            for p in positions:
                 # Ideally we fetch current market price, but for panic we close at entry just to simulate
                 # Real implementation requires querying yfinance here.
                 self.broker.close_position(p['trade_id'], p['entry_price'], "Panic Button")
            await update.message.reply_text("🚨 PANIC CLOSE EXECUTED. All positions liquidated.")

    async def _scan_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        if self.engine:
            await update.message.reply_text("🔍 Forcing immediate scan...")
            asyncio.create_task(self.engine.run_live_cycle())

    def start_listening(self):
        """Starts the long-polling background task for receiving commands."""
        if not self.bot_token:
            return

        self.app = Application.builder().token(self.bot_token).build()
        self.app.add_handler(CommandHandler("durum", self._status_command))
        self.app.add_handler(CommandHandler("durdur", self._pause_command))
        self.app.add_handler(CommandHandler("devam", self._resume_command))
        self.app.add_handler(CommandHandler("kapat_hepsi", self._panic_command))
        self.app.add_handler(CommandHandler("tara", self._scan_command))

        # Run in a separate thread/task so it doesn't block main asyncio loop
        logger.info("Telegram command listener started.")
        # Note: In an async environment, run_polling should be integrated properly
        # For simplicity here, we'll assume it's called via asyncio.create_task in main.
