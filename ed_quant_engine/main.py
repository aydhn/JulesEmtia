import asyncio
import schedule
import time
import os
import gc
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ED Capital Modules
from src.logger import quant_logger
from src.config import TICKERS, MAX_POSITIONS, MAX_GLOBAL_RISK_PCT
from src.paper_db import PaperDB
from src.notifier import TelegramNotifier
from src.data_loader import DataLoader
from src.features import FeatureEngineer
from src.filters import MarketFilters
from src.sentiment_filter import NLPSentimentFilter
from src.ml_validator import MLValidator
from src.broker import PaperBroker
from src.strategy import StrategyEngine
from src.portfolio_manager import PortfolioManager
from src.reporter import Reporter
from src.monte_carlo import MonteCarloSimulator

class QuantEngine:
    def __init__(self):
        self.is_paused = False
        self.db = PaperDB()
        self.broker = PaperBroker(self.db)
        self.notifier = TelegramNotifier()
        self.data_loader = DataLoader()
        self.nlp = NLPSentimentFilter()
        self.ml = MLValidator()
        self.telegram_app = None
        self.admin_id = int(os.getenv("ADMIN_CHAT_ID", 0))

    # --- TELEGRAM ADMIN COMMANDS ---
    async def _auth(self, update: Update) -> bool:
        if update.effective_user.id != self.admin_id:
            quant_logger.critical(f"Unauthorized access attempt by ID {update.effective_user.id}")
            return False
        return True

    async def cmd_durum(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._auth(update): return
        bal = self.broker.get_account_balance()
        pos = self.broker.get_open_positions()
        msg = f"📊 *ED Capital Durum*\nBakiye: ${bal:,.2f}\nAçık Pozisyonlar: {len(pos)}\n"
        for p in pos:
            msg += f"• {p['ticker']} {p['direction']} (P: {p['entry_price']:.4f})\n"
        await update.message.reply_text(msg, parse_mode='Markdown')

    async def cmd_durdur(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._auth(update): return
        self.is_paused = True
        await update.message.reply_text("🛑 Sistem duraklatıldı. Sadece açık pozisyonlar yönetilecek.")

    async def cmd_devam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._auth(update): return
        self.is_paused = False
        await update.message.reply_text("▶️ Sistem tam otonom taramaya devam ediyor.")

    async def cmd_kapat_hepsi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._auth(update): return
        pos = self.broker.get_open_positions()
        for p in pos:
            # Emergency close at market dummy price (in reality, fetch actual current price)
            self.broker.close_position(p['trade_id'], p['entry_price'], p['direction'], p['entry_price'], p['position_size'], 0.0)
        await update.message.reply_text("🚨 PANİK BUTONU AKTİF! Tüm pozisyonlar kapatıldı.")

    async def cmd_tara(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await self._auth(update): return
        await update.message.reply_text("🔍 Zorunlu tarama başlatılıyor...")
        asyncio.create_task(self.run_live_cycle())

    # --- CORE PIPELINE ---
    async def run_live_cycle(self):
        try:
            quant_logger.info("Starting live cycle pipeline...")

            # 1. Data Fetch
            data = await self.data_loader.fetch_all()
            if not data: return

            # 2. VIX Circuit Breaker & Macro
            is_black_swan = await MarketFilters.get_vix_status()

            open_positions = self.broker.get_open_positions()
            current_balance = self.broker.get_account_balance()

            # NLP Sentiment Cache
            sentiment_scores = await self.nlp.get_market_sentiment()

            # ML Training preparation dict
            htf_ltf_dict = {}

            for ticker, (df_htf, df_ltf) in data.items():
                if df_htf.empty or df_ltf.empty: continue

                # Align and Engineer Features
                df_htf = FeatureEngineer.apply_features(df_htf, is_htf=True)
                df_ltf = FeatureEngineer.apply_features(df_ltf, is_htf=False)
                df_merged = FeatureEngineer.align_mtf_data(df_htf, df_ltf)

                if df_merged.empty: continue
                htf_ltf_dict[ticker] = df_merged

                current_price = df_merged['Close'].iloc[-1]
                current_atr = df_merged.get('ATRr_14', current_price*0.01).iloc[-1]

                # Check Flash Crash
                if MarketFilters.check_flash_crash(df_merged):
                    continue

                # --- POSITION MANAGEMENT (Always runs, even if paused or Black Swan) ---
                pos_to_manage = [p for p in open_positions if p['ticker'] == ticker]
                for pos in pos_to_manage:
                    # If Black Swan, aggressive trailing stop
                    if is_black_swan: current_atr *= 0.5

                    action, new_val = StrategyEngine.check_trade_management(pos, current_price, current_atr)

                    if action in ['CLOSE_TP', 'CLOSE_SL']:
                        self.broker.close_position(pos['trade_id'], new_val, pos['direction'], pos['entry_price'], pos['position_size'], current_atr)
                        self.notifier.send_message(f"✅ İşlem Kapandı: {ticker} {pos['direction']}")
                    elif action == 'UPDATE_SL':
                        self.broker.modify_trailing_stop(pos['trade_id'], new_val)

                # --- NEW SIGNAL GENERATION ---
                if self.is_paused or is_black_swan: continue
                if len(open_positions) >= MAX_POSITIONS: continue

                signal = StrategyEngine.check_signals(df_merged)
                if signal:
                    # 1. ML Validator
                    if not self.ml.validate_signal(df_merged.iloc[-1]): continue

                    # 2. NLP Sentiment Veto
                    cat = "Gold" if "GC" in ticker else ("Oil" if "CL" in ticker else "Forex")
                    if signal == 'Long' and sentiment_scores.get(cat, 0) < -0.4:
                        quant_logger.warning(f"Sentiment Veto for {ticker}")
                        continue

                    # 3. Correlation Veto
                    corr_matrix = PortfolioManager.calculate_correlation_matrix(htf_ltf_dict)
                    if PortfolioManager.correlation_veto(ticker, signal, open_positions, corr_matrix):
                        continue

                    # 4. Sizing (Kelly)
                    closed_trades = self.db.get_all_closed_trades_df()
                    f_kelly = PortfolioManager.calculate_kelly_fraction(closed_trades)
                    sl, tp = StrategyEngine.calculate_dynamic_risk(current_price, current_atr, signal)
                    size = PortfolioManager.get_position_size(current_balance, current_price, sl, f_kelly)

                    if size <= 0: continue

                    # Execute!
                    trade_id = self.broker.place_market_order(ticker, signal, size, current_price, current_atr, sl, tp)
                    if trade_id:
                        msg = f"🚀 *YENİ İŞLEM*\nTicker: {ticker}\nYön: {signal}\nGiriş: {current_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nLot: {size:.4f}"
                        self.notifier.send_message(msg)

            # Garbage Collection
            del data, htf_ltf_dict
            gc.collect()
            quant_logger.info("Cycle complete.")

        except Exception as e:
            quant_logger.error(f"Error in live cycle: {e}")

    # --- SCHEDULING & LIFECYCLE ---
    async def heartbeat(self):
        bal = self.broker.get_account_balance()
        self.notifier.send_message(f"🟢 ED Capital Sistem Aktif\nBakiye: ${bal:,.2f}")

    async def weekly_retrain(self):
        quant_logger.info("Starting weekend ML retrain task...")
        data = await self.data_loader.fetch_all()
        # simplified align logic for retrain
        merged_data = {}
        for t, (df_h, df_l) in data.items():
            if not df_h.empty and not df_l.empty:
                df_h = FeatureEngineer.apply_features(df_h, True)
                df_l = FeatureEngineer.apply_features(df_l, False)
                merged_data[t] = FeatureEngineer.align_mtf_data(df_h, df_l)
        self.ml.train_model(merged_data)

    async def generate_report(self):
        closed = self.db.get_all_closed_trades_df()
        bal = self.broker.get_account_balance()
        mc_res = MonteCarloSimulator.run_simulation(closed)
        pdf = Reporter.generate_html_tearsheet(closed, bal, mc_res)
        if pdf: self.notifier.send_document(pdf, "ED Capital Haftalık Performans Raporu")

    async def run_bot(self):
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if bot_token:
            self.telegram_app = Application.builder().token(bot_token).build()
            self.telegram_app.add_handler(CommandHandler("durum", self.cmd_durum))
            self.telegram_app.add_handler(CommandHandler("durdur", self.cmd_durdur))
            self.telegram_app.add_handler(CommandHandler("devam", self.cmd_devam))
            self.telegram_app.add_handler(CommandHandler("kapat_hepsi", self.cmd_kapat_hepsi))
            self.telegram_app.add_handler(CommandHandler("tara", self.cmd_tara))
            await self.telegram_app.initialize()
            await self.telegram_app.start()
            await self.telegram_app.updater.start_polling()
            self.notifier.send_message("🚀 ED Capital Quant Engine Başlatıldı!")

        # Sync schedule inside Async loop
        schedule.every().hour.at(":00").do(lambda: asyncio.create_task(self.run_live_cycle()))
        schedule.every().day.at("08:00").do(lambda: asyncio.create_task(self.heartbeat()))
        schedule.every().friday.at("23:00").do(lambda: asyncio.create_task(self.generate_report()))
        schedule.every().saturday.at("10:00").do(lambda: asyncio.create_task(self.weekly_retrain()))

        while True:
            schedule.run_pending()
            await asyncio.sleep(1)

if __name__ == "__main__":
    engine = QuantEngine()
    try:
        asyncio.run(engine.run_bot())
    except KeyboardInterrupt:
        quant_logger.info("System shutting down...")
