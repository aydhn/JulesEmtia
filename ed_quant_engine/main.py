import asyncio
import schedule
import time
import os
import gc
import traceback
from datetime import datetime

# Import ED Capital modules
from core.config import TICKERS, MAX_POSITIONS, MAX_GLOBAL_RISK_PCT
from core.infrastructure import PaperDB, PaperBroker, logger
from core.data_engine import DataEngine, SentimentEngine
from core.quant_models import RiskManager, MLValidator
from core.quant_logic import Strategy
from core.analysis import Analyzer
from system.telegram_bot import tg

class QuantEngine:
    def __init__(self):
        self.db = PaperDB()
        self.broker = PaperBroker(self.db)
        self.data_engine = DataEngine(TICKERS)
        self.sentiment = SentimentEngine()
        self.risk_manager = RiskManager()
        self.ml_validator = MLValidator()

        # Connect DB instance internally for old managers if needed
        from core.data_engine import db as global_db
        self.global_db = global_db
        self.global_db.init_db()

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

            # Align data for later steps (needed for risk manager to get current prices/atrs)
            aligned_data = {}
            current_prices = {}
            current_atrs = {}

            from core.quant_models import add_features

            for t, data in htf_ltf_dict.items():
                # Get the aligned dataframe to extract current attributes
                # Note: strategy.generate_signal aligns data internally, but we need current attrs here.
                # Let's quickly get the latest close and ATR
                ltf = data['ltf']
                if len(ltf) > 0:
                    current_prices[t] = ltf['Close'].iloc[-1]
                    # Approximate ATR if not calculated yet
                    current_atrs[t] = current_prices[t] * 0.01

            # --- POSITION MANAGEMENT ---
            self.risk_manager.manage_positions(self.broker, current_prices, current_atrs, is_black_swan)

            if tg.is_paused or is_black_swan:
                return

            # NLP Sentiment Cache
            for cat in TICKERS.keys():
                await self.sentiment.fetch_sentiment(cat)

            # Correlation matrix requires historical closes
            # Let's build a quick dataframe for correlation
            corr_df = pd.DataFrame()
            import pandas as pd
            for t, data in htf_ltf_dict.items():
                if len(data['ltf']) > 0:
                    corr_df[t] = data['ltf']['Close'].tail(50)
            corr_matrix = corr_df.corr()

            # --- SIGNAL GENERATION ---
            open_pos = self.db.get_open_trades()
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

                # 1. ML Validator
                # To validate, we need the latest feature row. Strategy aligned it internally.
                # Re-aligning quickly to get features for ML
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
                cat = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")
                sentiment_score = self.sentiment.cache.get(cat, (0, 0))[0]

                if (direction == "LONG" and sentiment_score < -0.3) or (direction == "SHORT" and sentiment_score > 0.3):
                    logger.warning(f"Sentiment Veto: Rejected {direction} on {ticker} due to news sentiment ({sentiment_score:.2f}).")
                    continue

                # 3. Correlation & Exposure Veto
                if not self.risk_manager.check_portfolio_limits(ticker, direction, corr_matrix):
                    continue

                # 4. Sizing & Execution
                # SL / TP
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
        report_path = Analyzer.generate_tear_sheet()
        if os.path.exists("tear_sheet.html"):
            await tg.send_document("tear_sheet.html", "ED Capital Haftalık Performans Raporu")
        else:
            await tg.send_msg(f"Rapor Hatası: {report_path}")

    async def run_bot(self):
        # Initialize Telegram
        await tg.start(run_live_cycle_ref=self.run_live_cycle)
        await tg.send_msg("🚀 ED Capital Quant Engine Başlatıldı!")

        # Async scheduling loop
        schedule.every().hour.at(":00").do(lambda: asyncio.create_task(self.run_live_cycle()))
        schedule.every().day.at("08:00").do(lambda: asyncio.create_task(self.heartbeat()))
        schedule.every().friday.at("23:00").do(lambda: asyncio.create_task(self.generate_report()))

        while True:
            schedule.run_pending()
            await asyncio.sleep(1)

if __name__ == "__main__":
    engine = QuantEngine()
    try:
        asyncio.run(engine.run_bot())
    except KeyboardInterrupt:
        logger.info("System shutting down manually.")
