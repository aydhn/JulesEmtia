import asyncio
import schedule
import logging
from datetime import datetime
import gc
import traceback
import pandas as pd
import os

from src.broker import PaperBroker
from src.data_engine import DataEngine
from src.macro_filter import MacroFilter
from src.sentiment_filter import SentimentEngine
from src.portfolio_manager import PortfolioManager
from src.execution import ExecutionModel
from src.features import calculate_mtf_features
from src.strategy import Strategy
from src.notifier import tg_bot
from src.config import TICKERS

# Newly added modules
from src.ml_validator import MLValidator
from src.reporter import Reporter
from src.monte_carlo import MonteCarloSimulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/quant_engine.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("QuantEngine")

class EDQuantEngine:
    def __init__(self):
        self.broker = PaperBroker()
        self.data_engine = DataEngine(TICKERS)
        self.macro = MacroFilter()
        self.sentiment = SentimentEngine()
        self.portfolio = PortfolioManager(self.broker)
        self.execution = ExecutionModel()

        # Phase 18: ML Validator
        self.ml_validator = MLValidator()

        # Phase 13 & 22: Reporting & Risk
        self.reporter = Reporter()
        self.monte_carlo = MonteCarloSimulator()

    def get_status_report(self) -> str:
        bal = self.broker.get_account_balance()
        open_pos = self.broker.get_open_positions()
        pos_str = "\n".join([f"• {p['ticker']} {p['direction']} (Pnl: {p['pnl']:.2f})" for p in open_pos]) if open_pos else "Yok"

        # Add Monte Carlo Risk of Ruin to status if possible
        mc_res = self.monte_carlo.run_simulation()
        risk_str = f"İflas Riski: %{mc_res.get('risk_of_ruin', 0)*100:.2f}" if "error" not in mc_res else "Risk Verisi Yetersiz"

        return f"🟢 ED Capital Durum\nKasa: ${bal:,.2f}\n{risk_str}\nAçık Pozisyonlar ({len(open_pos)}):\n{pos_str}"

    async def panic_close_all(self):
        open_pos = self.broker.get_open_positions()
        for pos in open_pos:
            self.broker.close_position(pos['trade_id'], pos['exit_price'] if pos['exit_price'] else pos['entry_price'])
        await tg_bot.send_message("🚨 Tüm pozisyonlar acil durum protokolüyle piyasa fiyatından kapatıldı.")

    async def generate_weekly_report(self):
        """Phase 13: Generate Tear Sheet and send via Telegram."""
        logger.info("Generating weekly Tear Sheet...")
        try:
            report_path = self.reporter.generate_html_report()
            if os.path.exists(report_path):
                await tg_bot.send_document(report_path, "ED Capital - Haftalık Piyasa Genel Bakış")
        except Exception as e:
            logger.error(f"Report generation failed: {e}")

    async def run_ml_retraining(self):
        """Phase 18: Autonomous ML Retraining."""
        logger.info("Starting weekly ML retraining process...")
        try:
            all_historical_data = pd.DataFrame()
            for ticker in self.data_engine.all_tickers:
                htf, ltf = await self.data_engine.fetch_mtf_data(ticker)
                if not htf.empty and not ltf.empty:
                    merged = self.data_engine.merge_mtf_data(htf, ltf)
                    features_df = calculate_mtf_features(htf, ltf) # Merge handles inside here as well if not careful
                    all_historical_data = pd.concat([all_historical_data, features_df])

            if not all_historical_data.empty:
                self.ml_validator.train(all_historical_data)
                await tg_bot.send_message("🧠 *Makine Öğrenmesi Modeli (Random Forest) başarıyla yeniden eğitildi.*")
        except Exception as e:
            logger.error(f"ML retraining failed: {e}")

    async def run_live_cycle(self):
        logger.info("Starting live evaluation cycle...")
        htf_ltf = {}
        try:
            if tg_bot.is_paused:
                logger.info("System is Paused. Skipping new signals.")

            await self.macro.fetch_macro_data()
            is_black_swan = self.macro.is_black_swan()

            for ticker in self.data_engine.all_tickers:
                htf, ltf = await self.data_engine.fetch_mtf_data(ticker)
                if not htf.empty and not ltf.empty:
                    htf_ltf[ticker] = {"htf": htf, "ltf": ltf}

            if not htf_ltf: return

            # Manage Open Positions
            open_pos = self.broker.get_open_positions()
            for pos in open_pos:
                ticker = pos['ticker']
                if ticker not in htf_ltf: continue

                curr_price = float(htf_ltf[ticker]['ltf']['Close'].iloc[-1])
                # Attempt to get ATR, fallback to 1%
                atr_series = htf_ltf[ticker]['ltf'].get('ATR_14')
                atr = float(atr_series.iloc[-1]) if atr_series is not None else curr_price * 0.01

                # Check Circuit Breakers
                if is_black_swan or self.macro.is_flash_crash(htf_ltf[ticker]['ltf']):
                    self.broker.close_position(pos['trade_id'], curr_price)
                    await tg_bot.send_message(f"🚨 CIRCUIT BREAKER: Closed {ticker}")
                    continue

                # TP / SL Check
                if (pos['direction'] == "LONG" and (curr_price <= pos['sl_price'] or curr_price >= pos['tp_price'])) or \
                   (pos['direction'] == "SHORT" and (curr_price >= pos['sl_price'] or curr_price <= pos['tp_price'])):
                    res = self.broker.close_position(pos['trade_id'], curr_price)
                    await tg_bot.send_message(f"🔒 İŞLEM KAPANDI: {ticker} (PnL: {res.get('pnl', 0):.2f})")
                    continue

                # Trailing Stop & Breakeven Check
                new_sl = pos['sl_price']
                if pos['direction'] == "LONG":
                    if curr_price >= pos['entry_price'] + (1.0 * atr) and pos['sl_price'] < pos['entry_price']:
                        new_sl = pos['entry_price']
                    calc_sl = curr_price - (1.5 * atr)
                    if calc_sl > new_sl: new_sl = calc_sl
                else:
                    if curr_price <= pos['entry_price'] - (1.0 * atr) and pos['sl_price'] > pos['entry_price']:
                        new_sl = pos['entry_price']
                    calc_sl = curr_price + (1.5 * atr)
                    if calc_sl < new_sl: new_sl = calc_sl

                if new_sl != pos['sl_price']:
                    self.broker.modify_trailing_stop(pos['trade_id'], new_sl)

            if tg_bot.is_paused or is_black_swan:
                return

            corr_matrix = self.portfolio.calculate_correlation_matrix({t: d['ltf'] for t, d in htf_ltf.items()})

            for category in TICKERS.keys():
                await self.sentiment.fetch_sentiment(category)

            current_balance = self.broker.get_account_balance()
            kelly_fraction = self.portfolio.calculate_kelly_fraction()

            for ticker, data in htf_ltf.items():
                if self.macro.is_flash_crash(data['ltf']): continue

                merged_features = calculate_mtf_features(data['htf'], data['ltf'])
                signal = Strategy.generate_signal(merged_features)

                if not signal: continue
                direction = signal['dir']
                curr_price = float(signal['price'])
                atr = float(signal['atr'])

                cat = next((k for k, v in TICKERS.items() if ticker in v), "FOREX")

                # Phase 6: Macro Regime Veto
                if self.macro.get_regime_veto(direction, cat): continue
                # Phase 18: ML Validator Veto
                if not self.ml_validator.validate_signal(merged_features, direction): continue
                # Phase 20: Sentiment Veto
                if self.sentiment.get_sentiment_veto(direction, cat): continue
                # Phase 11: Correlation Veto
                if self.portfolio.check_correlation_veto(ticker, direction, corr_matrix): continue

                risk_amount = current_balance * kelly_fraction
                lot_size = risk_amount / (1.5 * atr)

                if lot_size <= 0: continue

                spread, slippage = self.execution.calculate_costs(ticker, curr_price, atr)

                sl = curr_price - (1.5 * atr) if direction == "LONG" else curr_price + (1.5 * atr)
                tp = curr_price + (3.0 * atr) if direction == "LONG" else curr_price - (3.0 * atr)

                receipt = self.broker.place_market_order(ticker, direction, lot_size, curr_price, sl, tp, spread, slippage)

                await tg_bot.send_message(
                    f"🚀 *YENİ İŞLEM*\n"
                    f"Varlık: {ticker}\n"
                    f"Yön: {direction}\n"
                    f"Giriş: {receipt['executed_price']:.4f}\n"
                    f"SL: {sl:.4f} | TP: {tp:.4f}\n"
                    f"Lot: {lot_size:.4f} (Risk: %{kelly_fraction*100:.2f})"
                )

        except Exception as e:
            logger.error(f"Live cycle error: {e}\n{traceback.format_exc()}")
        finally:
            del htf_ltf
            gc.collect()

async def main_loop():
    engine = EDQuantEngine()

    await tg_bot.start_polling(
        get_status_cb=engine.get_status_report,
        close_all_cb=engine.panic_close_all,
        scan_cb=engine.run_live_cycle
    )

    await tg_bot.send_message("🟢 *ED Capital Quant Engine* başlatıldı.")

    # Phase 23: Candle-Close Synchronization Scheduling
    schedule.every().hour.at(":01").do(lambda: asyncio.create_task(engine.run_live_cycle()))
    # Phase 13: Weekly Tear Sheet Reporting
    schedule.every().friday.at("23:00").do(lambda: asyncio.create_task(engine.generate_weekly_report()))
    # Phase 18: Weekly Auto-Retraining
    schedule.every().sunday.at("02:00").do(lambda: asyncio.create_task(engine.run_ml_retraining()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    asyncio.run(main_loop())
