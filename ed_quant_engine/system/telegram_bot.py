from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from core.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
import asyncio
from system.logger import log

class TelegramManager:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN:
            log.warning("TELEGRAM_BOT_TOKEN not found in env.")
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build() if TELEGRAM_BOT_TOKEN else None
        self.is_paused = False

        # Will hold a reference to main.py's run_live_cycle for forced scans
        self.run_live_cycle_ref = None

        if self.app:
            self._setup_handlers()

    def _setup_handlers(self):
        def admin_only(func):
            async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if update.effective_user.id != ADMIN_CHAT_ID:
                    log.warning(f"Unauthorized access attempt from {update.effective_user.id}")
                    return
                return await func(update, context)
            return wrapper

        @admin_only
        async def cmd_durum(update, context):
            import sqlite3
            import pandas as pd
            try:
                conn = sqlite3.connect("paper_db.sqlite3")
                df = pd.read_sql_query("SELECT * FROM trades WHERE status='OPEN'", conn)
                open_pos_count = len(df)
                conn.close()
            except:
                open_pos_count = 0

            await update.message.reply_text(f"📊 Açık Pozisyon: {open_pos_count}\nDurum: {'DURAKLATILDI' if self.is_paused else 'AKTİF'}")

        @admin_only
        async def cmd_durdur(update, context):
            self.is_paused = True
            await update.message.reply_text("🛑 Sistem Duraklatıldı. İzleyen stoplar koruma modunda çalışmaya devam ediyor.")

        @admin_only
        async def cmd_devam(update, context):
            self.is_paused = False
            await update.message.reply_text("▶️ Sistem Tekrar Aktif.")

        @admin_only
        async def cmd_kapat_hepsi(update, context):
            # Panic Button - close all immediately
            from core.data_engine import db
            import yfinance as yf

            open_pos = db.get_open_positions()
            if open_pos.empty:
                await update.message.reply_text("Açık pozisyon yok.")
                return

            await update.message.reply_text("🚨 PANİK MODU: Tüm açık pozisyonlar piyasa fiyatından kapatılıyor...")

            for _, row in open_pos.iterrows():
                try:
                    tid, t, dir, size = row['trade_id'], row['ticker'], row['direction'], row['position_size']
                    e_p = row['entry_price']

                    # Fetch current price quickly
                    curr_p = yf.download(t, period="1d", interval="1m", progress=False)['Close'].iloc[-1]
                    pnl = (curr_p - e_p) * size if dir == 'LONG' else (e_p - curr_p) * size

                    db.close_trade(tid, curr_p, pnl)
                    log.critical(f"PANIC CLOSE: {t} kapandı. PnL: {pnl:.2f}")
                except Exception as e:
                    log.error(f"Failed to panic close {t}: {e}")

            await update.message.reply_text("✅ Panik kapatması tamamlandı.")

        @admin_only
        async def cmd_tara(update, context):
            await update.message.reply_text("🔍 Manuel tarama başlatılıyor...")
            if self.run_live_cycle_ref:
                asyncio.create_task(self.run_live_cycle_ref())
                await update.message.reply_text("✅ Tarama görevi sıraya eklendi.")
            else:
                await update.message.reply_text("❌ Tarama fonksiyonu tanımlı değil.")

        self.app.add_handler(CommandHandler("durum", cmd_durum))
        self.app.add_handler(CommandHandler("durdur", cmd_durdur))
        self.app.add_handler(CommandHandler("devam", cmd_devam))
        self.app.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
        self.app.add_handler(CommandHandler("tara", cmd_tara))

    async def send_document(self, doc_path: str, caption: str = ""):
        if self.app and ADMIN_CHAT_ID:
            try:
                with open(doc_path, "rb") as doc:
                    await self.app.bot.send_document(chat_id=ADMIN_CHAT_ID, document=doc, caption=caption)
            except Exception as e:
                log.error(f"Telegram Send Doc Error: {e}")

    async def send_msg(self, text: str):
        if self.app and ADMIN_CHAT_ID:
            try:
                await self.app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)
            except Exception as e:
                log.error(f"Telegram Send Error: {e}")

    async def start(self, run_live_cycle_ref=None):
        self.run_live_cycle_ref = run_live_cycle_ref
        if self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

tg = TelegramManager()
