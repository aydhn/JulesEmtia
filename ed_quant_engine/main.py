import asyncio
import schedule
import time
import os
import gc
import traceback
import pandas as pd
from datetime import datetime

# Import ED Capital modules
from core.config import TICKERS
from core.infrastructure import db, PaperBroker, logger
from core.data_engine import DataEngine
from core.ai_filters import SentimentEngine, MLValidator
from core.risk_manager import RiskManager
from core.quant_logic import Strategy
from core.reporter import Reporter
from system.telegram_bot import tg

class QuantEngine:
    def __init__(self):
        self.db = db
        self.broker = PaperBroker(self.db)
        self.data_engine = DataEngine(TICKERS)
        self.sentiment = SentimentEngine()
        self.risk_manager = RiskManager(self.db)
        self.ml_validator = MLValidator()

    async def run_live_cycle(self):
        try:
            logger.info("Starting live cycle pipeline...")

            if tg.is_paused:
                logger.info("System is paused. Skipping signal generation, only managing open positions.")

            # 1. Fetch MTF Data
            htf_ltf_dict = {}
            for ticker in self.data_engine.all_tickers:
                htf, ltf = await self.data_engine.fetch_mtf_data(ticker)
                if htf is not None and ltf is not None:
                    htf_ltf_dict[ticker] = {"htf": htf, "ltf": ltf}

            if not htf_ltf_dict:
                logger.warning("No data fetched. Aborting cycle.")
                return

            # 2. VIX Circuit Breaker & Macro
            is_black_swan = self.risk_manager.check_black_swan()
            macro_data = await self.data_engine.fetch_macro_data()

            current_prices = {}
            current_atrs = {}

            from core.quant_models import add_features

            for t, data in htf_ltf_dict.items():
                ltf = data['ltf']
                if len(ltf) > 0:
                    current_prices[t] = ltf['Close'].iloc[-1]
                    current_atrs[t] = current_prices[t] * 0.01 # Approximation if not calculated

            # --- POSITION MANAGEMENT ---
            self.risk_manager.manage_positions(self.broker, current_prices, current_atrs, is_black_swan)

            if tg.is_paused or is_black_swan:
                return

            # NLP Sentiment Cache
            for cat in TICKERS.keys():
                await self.sentiment.fetch_sentiment(cat)

            # Correlation matrix requires historical closes
            corr_df = pd.DataFrame()
            for t, data in htf_ltf_dict.items():
                if len(data['ltf']) > 0:
                    corr_df[t] = data['ltf']['Close'].tail(50)
            corr_matrix = corr_df.corr()

            # --- SIGNAL GENERATION ---
            current_balance = self.db.get_balance()

            for ticker, data in htf_ltf_dict.items():
                # Check Flash Crash
                if self.risk_manager.check_z_score_anomaly(ticker, data['ltf']):
                    continue

                signal_data = Strategy.generate_signal(data['htf'], data['ltf'])
                if not signal_data:
                    continue

                direction = signal_data['dir']
                curr_p = signal_data['price']
                atr = signal_data['atr']

                cat = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")

                # 0. Macro Veto
                if self.risk_manager.check_macro_veto(direction, cat, macro_data):
                    continue

                # 1. ML Validator
                htf_f = add_features(data['htf'].copy())
                ltf_f = add_features(data['ltf'].copy())

                if htf_f.empty or ltf_f.empty: continue

                htf_shifted = htf_f.shift(1).reset_index()
                ltf_reset = ltf_f.reset_index()
                if 'Date' not in ltf_reset.columns and 'Datetime' in ltf_reset.columns:
                    ltf_reset.rename(columns={'Datetime': 'Date'}, inplace=True)
                if 'Date' not in htf_shifted.columns and 'Datetime' in htf_shifted.columns:
                    htf_shifted.rename(columns={'Datetime': 'Date'}, inplace=True)

                merged_features = pd.merge_asof(ltf_reset, htf_shifted, on='Date', direction='backward', suffixes=('', '_HTF'))

                if not self.ml_validator.validate_signal(merged_features, direction):
                    continue

                # 2. NLP Sentiment Veto
                if self.sentiment.get_sentiment_veto(direction, cat):
                    continue

                # 3. Correlation & Exposure Veto
                if not self.risk_manager.check_portfolio_limits(ticker, direction, corr_matrix):
                    continue

                # 4. Sizing & Execution
                if direction == 'LONG':
                    sl = curr_p - (1.5 * atr)
                    tp = curr_p + (3.0 * atr)
                else:
                    sl = curr_p + (1.5 * atr)
                    tp = curr_p - (3.0 * atr)

                # Kelly sizing
                size = self.risk_manager.calculate_position_size(curr_p, atr, current_balance)
                if size <= 0: continue

                # Spread / Slippage
                spread, slippage = self.risk_manager.dynamic_spread_slippage(ticker, curr_p, atr)

                # Execute!
                self.broker.place_market_order(ticker, direction, size, sl, tp, curr_p, spread, slippage)
                await tg.send_msg(f"🚀 *YENİ İŞLEM*\nTicker: {ticker}\nYön: {direction}\nFiyat: {curr_p:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nLot: {size:.4f}")

            # Garbage Collection
            del htf_ltf_dict
            gc.collect()
            logger.info("Cycle complete.")

        except Exception as e:
            logger.error(f"Error in live cycle: {e}\n{traceback.format_exc()}")
            await tg.send_msg(f"⚠️ *System Error*: {e}")

    async def heartbeat(self):
        bal = self.broker.get_account_balance()
        open_pos = len(self.db.get_open_trades())
        await tg.send_msg(f"🟢 *ED Capital Sistem Aktif*\nBakiye: ${bal:,.2f}\nAçık Pozisyonlar: {open_pos}")

    async def generate_report(self):
        logger.info("Generating weekly report...")
        reporter = Reporter(self.db)
        report_path = reporter.generate_tear_sheet()
        if os.path.exists(report_path):
            await tg.send_document(report_path, "ED Capital Haftalık Performans Raporu")
        else:
            await tg.send_msg(f"Rapor Hatası: {report_path}")

    async def train_ml_model(self):
        """Phase 18: Otonom Yeniden Eğitim (Auto-Retraining)."""
        logger.info("Starting weekly ML retraining...")
        try:
            # Gather data for training
            all_data = pd.DataFrame()
            for ticker in self.data_engine.all_tickers:
                htf, ltf = await self.data_engine.fetch_mtf_data(ticker)
                if ltf is not None and not ltf.empty:
                    from core.quant_models import add_features
                    feat = add_features(ltf.copy())
                    all_data = pd.concat([all_data, feat])

            if not all_data.empty:
                self.ml_validator.train(all_data)
                await tg.send_msg("🧠 *ML Modeli Başarıyla Yeniden Eğitildi.*")
        except Exception as e:
            logger.error(f"ML Retraining Error: {e}")

    async def run_bot(self):
        # Initialize Telegram
        await tg.start(run_live_cycle_ref=self.run_live_cycle)
        await tg.send_msg("🚀 ED Capital Quant Engine Başlatıldı!")

        # Async scheduling loop
        schedule.every().hour.at(":01").do(lambda: asyncio.create_task(self.run_live_cycle()))
        schedule.every().day.at("08:00").do(lambda: asyncio.create_task(self.heartbeat()))
        schedule.every().friday.at("23:00").do(lambda: asyncio.create_task(self.generate_report()))
        schedule.every().sunday.at("02:00").do(lambda: asyncio.create_task(self.train_ml_model()))

        while True:
            schedule.run_pending()
            await asyncio.sleep(1)

if __name__ == "__main__":
    engine = QuantEngine()
    try:
        asyncio.run(engine.run_bot())
    except KeyboardInterrupt:
        logger.info("System shutting down manually.")
