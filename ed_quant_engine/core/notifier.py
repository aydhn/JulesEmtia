import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.logger import get_logger

logger = get_logger()

class TelegramManager:
    def __init__(self, token: str, admin_id: str, engine_ref=None):
        self.token = token
        self.admin_id = str(admin_id)
        self.engine = engine_ref

        if not self.token or self.token == "YOUR_TOKEN_HERE":
            logger.warning("Telegram token missing. Notifications disabled.")
            self.app = None
        else:
            self.app = ApplicationBuilder().token(self.token).build()
            self._register_commands()

    def _register_commands(self):
        self.app.add_handler(CommandHandler("durum", self.cmd_durum))
        self.app.add_handler(CommandHandler("durdur", self.cmd_durdur))
        self.app.add_handler(CommandHandler("devam", self.cmd_devam))
        self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_kapat_hepsi))
        self.app.add_handler(CommandHandler("tara", self.cmd_tara))

    async def _check_auth(self, update: Update) -> bool:
        if str(update.effective_chat.id) != self.admin_id:
            logger.critical(f"Yetkisiz Erişim Denemesi: {update.effective_chat.id}")
            return False
        return True

    async def send_message(self, message: str):
        if not self.app: return
        try:
            await self.app.bot.send_message(chat_id=self.admin_id, text=message)
        except Exception as e:
            logger.error(f"Telegram Mesaj Gönderimi Başarısız: {e}")

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update): return
        msg = f"🟢 Kasa: ${self.engine.capital:.2f}\nAçık Pozisyonlar: {len(self.engine.open_positions)}\nDurum: {'Duraklatıldı' if self.engine.is_paused else 'Aktif'}"
        await self.send_message(msg)

    async def cmd_durdur(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update): return
        self.engine.is_paused = True
        await self.send_message("Sistem Duraklatıldı: Yeni sinyal aranmayacak (Açık pozisyonların takibi devam ediyor).")

    async def cmd_devam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update): return
        self.engine.is_paused = False
        await self.send_message("Sistem Aktif: Otonom tarama moduna dönüldü.")

    async def cmd_kapat_hepsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update): return
        await self.engine.panic_close_all()
        await self.send_message("🚨 PANİK KAPATMASI YAPILDI: Tüm işlemler piyasa fiyatından kapatıldı.")

    async def cmd_tara(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._check_auth(update): return
        await self.send_message("Manuel Tarama Tetikleniyor...")
        await self.engine.run_live_cycle()

    async def start_polling(self):
        """Used internally or if running as a standalone task"""
        if self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
