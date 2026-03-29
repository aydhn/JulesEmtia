import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from core.logger import get_logger

logger = get_logger()

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
