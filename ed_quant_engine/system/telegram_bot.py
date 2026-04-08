from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import sqlite3
import pandas as pd
from core.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from .logger import log

class TelegramManager:
    def __init__(self):
        if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN":
            log.warning("TELEGRAM_BOT_TOKEN not found in env.")
        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build() if TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN" else None
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
            try:
                conn = sqlite3.connect("data/paper_db.sqlite3")
                df = pd.read_sql_query("SELECT * FROM trades WHERE status='Open'", conn)

                cursor = conn.cursor()
                cursor.execute("SELECT current_balance FROM balance WHERE id=1")
                bal_row = cursor.fetchone()
                balance = bal_row[0] if bal_row else 0.0

                open_pos_count = len(df)
                conn.close()

                msg = f"📊 *ED Capital Durum*\nBakiye: ${balance:,.2f}\nAçık Pozisyon: {open_pos_count}\nDurum: {'DURAKLATILDI' if self.is_paused else 'AKTİF'}\n"
                for _, row in df.iterrows():
                    msg += f"• {row['ticker']} {row['direction']} (Giriş: {row['entry_price']:.4f})\n"
                await update.message.reply_text(msg, parse_mode='Markdown')
            except Exception as e:
                log.error(f"Status Error: {e}")
                await update.message.reply_text("❌ Durum alınamadı.")

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
            from core.infrastructure import PaperDB
            import yfinance as yf

            db = PaperDB()
            open_pos = db.get_open_trades()

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
                    pnl = (curr_p - e_p) * size if dir == 'Long' else (e_p - curr_p) * size

                    with db._get_conn() as conn:
                        conn.execute("UPDATE trades SET status = 'Closed', exit_time = datetime('now'), exit_price = ?, pnl = ? WHERE trade_id = ?", (curr_p, pnl, tid))
                        conn.commit()

                    new_balance = db.get_balance() + pnl
                    db.update_balance(new_balance)

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
                await self.app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode='Markdown')
            except Exception as e:
                log.error(f"Telegram Send Error: {e}")

    async def start(self, run_live_cycle_ref=None):
        self.run_live_cycle_ref = run_live_cycle_ref
        if self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()

tg = TelegramManager()
