import os
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from core.logger import logger
import pandas as pd

class TelegramNotifier:
    def __init__(self, db_instance):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "dummy")
        admin_id_str = os.getenv("ADMIN_CHAT_ID", "0")
        self.admin_id = int(admin_id_str) if admin_id_str.isdigit() else 0

        self.db = db_instance
        self.is_paused = False

        # Callbacks that will be injected from main.py
        self.run_live_cycle = None
        self.panic_close_all = None

        if self.token != "dummy":
            self.app = Application.builder().token(self.token).build()
            self.app.add_handler(CommandHandler("durum", self.cmd_status))
            self.app.add_handler(CommandHandler("durdur", self.cmd_pause))
            self.app.add_handler(CommandHandler("devam", self.cmd_resume))
            self.app.add_handler(CommandHandler("tara", self.cmd_scan))
            self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_panic_close))
        else:
            self.app = None

    async def verify_admin(self, update: Update) -> bool:
        if update.effective_user.id != self.admin_id:
            logger.critical(f"Yetkisiz Erişim Denemesi: {update.effective_user.id}")
            return False
        return True

    async def send_message(self, text: str):
        if not self.app:
            logger.info(f"Telegram Simulator: {text}")
            return
        try:
            await self.app.bot.send_message(chat_id=self.admin_id, text=text, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Telegram Gönderim Hatası: {e}")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.verify_admin(update): return
        open_trades = self.db.get_open_trades()

        closed_trades = pd.read_sql("SELECT * FROM trades WHERE status='Closed'", self.db.conn)
        total_pnl = closed_trades['pnl'].sum() if not closed_trades.empty else 0.0

        msg = f"📊 <b>SİSTEM DURUMU</b>\nDuraklatıldı: {self.is_paused}\nAçık Pozisyonlar: {len(open_trades)}\nToplam Gerçekleşen PnL: ${total_pnl:.2f}"

        if not open_trades.empty:
             msg += "\n\nAktif Pozisyonlar:\n"
             for _, row in open_trades.iterrows():
                 msg += f"- {row['ticker']} ({row['direction']}) | SL: {row['sl_price']:.2f}\n"

        await update.message.reply_text(msg, parse_mode='HTML')

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.verify_admin(update): return
        self.is_paused = True
        await update.message.reply_text("⏸️ Sistem yeni sinyal aramayı DURDURDU. Açık pozisyon takibi devam ediyor.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.verify_admin(update): return
        self.is_paused = False
        await update.message.reply_text("▶️ Sistem otonom taramaya DEVAM EDİYOR.")

    async def cmd_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.verify_admin(update): return
        await update.message.reply_text("🔎 <b>Manuel Tarama Başlatılıyor...</b>\nPiyasa fırsatları aranıyor.", parse_mode='HTML')
        if self.run_live_cycle:
             asyncio.create_task(self.run_live_cycle())
        else:
             await update.message.reply_text("Tarama fonksiyonu bulunamadı.")

    async def cmd_panic_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self.verify_admin(update): return
        await update.message.reply_text("🚨 <b>PANİK DÜĞMESİ TETİKLENDİ</b>\nTüm açık pozisyonlar piyasa fiyatından kapatılıyor...", parse_mode='HTML')
        if self.panic_close_all:
             asyncio.create_task(self.panic_close_all())
        else:
             await update.message.reply_text("Kapatma fonksiyonu bulunamadı.")
