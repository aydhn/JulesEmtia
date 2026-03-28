import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import os
import asyncio

# Phase 8: Profesyonel Loglama Altyapısı
os.makedirs("logs", exist_ok=True)
logger = logging.getLogger("EDCapitalQuant")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("logs/quant_engine.log", maxBytes=5*1024*1024, backupCount=3)
formatter = logging.Formatter('%(asctime)s - [%(levelname)s] - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Phase 5: Yerel Paper Trade Veritabanı
class PaperDB:
    def __init__(self, db_path="data/paper_db.sqlite3"):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cursor = self.conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT, direction TEXT, entry_time TEXT, entry_price REAL,
            sl_price REAL, tp_price REAL, position_size REAL, status TEXT,
            exit_time TEXT, exit_price REAL, pnl REAL, slippage_cost REAL
        )''')
        self.conn.commit()

    def execute_query(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor.lastrowid

    def fetch_all(self, query, params=()):
        return self.conn.cursor().execute(query, params).fetchall()

    def open_trade(self, ticker, direction, entry_price, sl_price, tp_price, position_size, slippage_cost=0.0):
        query = '''INSERT INTO trades (ticker, direction, entry_time, entry_price, sl_price, tp_price, position_size, status, slippage_cost)
                   VALUES (?, ?, datetime('now'), ?, ?, ?, ?, 'Open', ?)'''
        return self.execute_query(query, (ticker, direction, entry_price, sl_price, tp_price, position_size, slippage_cost))

    def close_trade(self, trade_id, exit_price, pnl):
        query = "UPDATE trades SET status = 'Closed', exit_time = datetime('now'), exit_price = ?, pnl = ? WHERE trade_id = ?"
        self.execute_query(query, (exit_price, pnl, trade_id))

# Phase 2 & 17: Çift Yönlü Telegram İletişimi ve Manuel Müdahale
class TelegramManager:
    def __init__(self, bot_token, admin_id, orchestrator_ref=None):
        self.bot_token = bot_token
        self.admin_id = int(admin_id) if admin_id else 0
        self.orchestrator = orchestrator_ref

        if self.bot_token and self.admin_id:
            self.app = ApplicationBuilder().token(self.bot_token).build()
            self._setup_handlers()
        else:
            self.app = None

    def _setup_handlers(self):
        self.app.add_handler(CommandHandler("durum", self.cmd_durum))
        self.app.add_handler(CommandHandler("durdur", self.cmd_durdur))
        self.app.add_handler(CommandHandler("devam", self.cmd_devam))
        self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_kapat_hepsi))
        self.app.add_handler(CommandHandler("tara", self.cmd_tara))

    async def _verify_admin(self, update: Update) -> bool:
        if update.effective_user.id != self.admin_id:
            logger.critical(f"Yetkisiz Erişim Denemesi: {update.effective_user.id}")
            return False
        return True

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        active_trades = len(self.orchestrator.open_positions)
        await update.message.reply_text(f"📊 Durum: {'Aktif' if not self.orchestrator.is_paused else 'Duraklatıldı'}\nKasa: ${self.orchestrator.capital:.2f}\nAçık Pozisyonlar: {active_trades}")

    async def cmd_durdur(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        self.orchestrator.is_paused = True
        logger.warning("Sistem Manuel Olarak Duraklatıldı.")
        await update.message.reply_text("⏸ Sistem Duraklatıldı. Yeni işlem aranmayacak, sadece mevcut pozisyonlar (Trailing Stop) izlenecek.")

    async def cmd_devam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        self.orchestrator.is_paused = False
        logger.info("Sistem Otonom Tarama Moduna Geri Döndü.")
        await update.message.reply_text("▶️ Sistem Otonom Tarama Moduna Geri Döndü.")

    async def cmd_kapat_hepsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        await update.message.reply_text("🚨 PANİK BUTONU TETİKLENDİ! Tüm işlemler piyasa fiyatından kapatılıyor...")
        await self.orchestrator.panic_close_all()

    async def cmd_tara(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._verify_admin(update): return
        await update.message.reply_text("🔍 Zorunlu Tarama Başlatıldı...")
        # Create a background task for scanning
        asyncio.create_task(self.orchestrator.run_live_cycle())

    async def send_message(self, text):
        if not self.app:
            logger.info(f"Telegram Simulator: {text}")
            return
        try:
            await self.app.bot.send_message(chat_id=self.admin_id, text=text)
        except Exception as e:
            logger.error(f"Telegram Gönderim Hatası: {e}")
