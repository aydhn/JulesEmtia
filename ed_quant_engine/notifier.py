from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from logger import logger
import config

class TelegramNotifier:
    def __init__(self):
        # Prevent initialization errors if token is missing
        if config.TELEGRAM_TOKEN == "DUMMY_TOKEN" or not config.TELEGRAM_TOKEN:
            logger.warning("Telegram token is missing or dummy. Bot won't run.")
            self.app = None
        else:
            self.app = Application.builder().token(config.TELEGRAM_TOKEN).build()
            self.admin_id = int(config.ADMIN_CHAT_ID)

            # Phase 17: Interactive Commands
            self.app.add_handler(CommandHandler("durum", self.cmd_durum))
            self.app.add_handler(CommandHandler("durdur", self.cmd_durdur))
            self.app.add_handler(CommandHandler("devam", self.cmd_devam))
            self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_panic))
            self.app.add_handler(CommandHandler("tara", self.cmd_force_scan))

        self.is_paused = False

    def _check_admin(self, update: Update) -> bool:
        user_id = update.effective_user.id
        if user_id != self.admin_id:
             logger.critical(f"Unauthorized Access Attempt: {user_id}")
             return False
        return True

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_admin(update): return

        # Phase 17: Fetch real data from paper_db and broker
        from paper_broker import PaperBroker
        broker = PaperBroker()
        bal = await broker.get_account_balance()
        pos = await broker.get_open_positions()

        msg = f"🟢 Sistem Aktif: {len(pos)} acik pozisyon. Bakiye: ${bal:.2f}"
        await update.message.reply_text(msg)

    async def cmd_durdur(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_admin(update): return
        self.is_paused = True
        await update.message.reply_text("⛔️ Tarama DURDURULDU. Acik pozisyon takibi devam ediyor.")

    async def cmd_devam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_admin(update): return
        self.is_paused = False
        await update.message.reply_text("▶️ Tarama DEVAM EDIYOR.")

    async def cmd_panic(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_admin(update): return
        self.is_paused = True

        from paper_broker import PaperBroker
        from data_loader import fetch_data_with_retry
        broker = PaperBroker()

        positions = await broker.get_open_positions()

        for pos in positions:
             trade_id = pos['trade_id']
             ticker = pos['ticker']
             # Fetch current market price to exit
             df = await fetch_data_with_retry(ticker, "1d", "1m", retries=1)
             exit_price = df['Close'].iloc[-1].item() if not df.empty else pos['entry_price']
             await broker.close_position(trade_id, exit_price)

        await update.message.reply_text(f"🚨 PANIK BUTONU: Tum acik {len(positions)} pozisyon kapatildi. Sistem durduruldu.")

    async def cmd_force_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._check_admin(update): return
        await update.message.reply_text("🔍 Taramaya Baslaniyor...")
        import main
        await main.run_live_cycle()

    async def start(self):
        if self.app:
            await self.app.initialize()
            await self.app.start()
            # Must run polling in background without blocking main event loop
            await self.app.updater.start_polling()
            logger.info("Telegram Bot started.")

    async def send_message(self, text):
        if self.app and self.admin_id:
            try:
                await self.app.bot.send_message(chat_id=self.admin_id, text=text)
            except Exception as e:
                logger.error(f"TG Send Error: {e}")

notifier = TelegramNotifier()