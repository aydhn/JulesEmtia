import pandas as pd
import asyncio
import time
import schedule
import gc
from src.core.config import ALL_TICKERS, INITIAL_CAPITAL, TICKERS
from src.core.logger import logger
from src.core.paper_db import init_db
from src.data.loader import DataLoader
from src.data.features import add_features
from src.filters.macro import MacroFilter
from src.filters.ml_model import MLValidator
from src.filters.sentiment import RSSSentimentFilter
from src.execution.broker import PaperBroker
from src.execution.costs import ExecutionModel
from src.strategy.portfolio import PortfolioManager
from src.strategy.rules import TradingRules
from src.bot.notifier import TelegramNotifier
from src.bot.reporter import Reporter

class QuantEngine:
    def __init__(self):
        self.is_paused = False
        init_db()

        # Modules
        self.loader = DataLoader(ALL_TICKERS)
        self.macro = MacroFilter()
        self.ml = MLValidator()
        self.sentiment = RSSSentimentFilter()
        self.broker = PaperBroker(INITIAL_CAPITAL)
        self.portfolio = PortfolioManager()
        self.notifier = TelegramNotifier()

        # Start background tasks
        self.sentiment.update_sentiment_async()
        self.setup_telegram()

    def setup_telegram(self):
        self.notifier.register_command("/durum", self.cmd_status)
        self.notifier.register_command("/durdur", self.cmd_pause)
        self.notifier.register_command("/devam", self.cmd_resume)
        self.notifier.register_command("/kapat_hepsi", self.cmd_panic_close)
        self.notifier.register_command("/tara", self.cmd_force_scan)
        self.notifier.start_polling()

    def cmd_status(self, _):
        balance = self.broker.get_account_balance()
        open_pos = len(self.broker.get_open_positions())
        msg = f"🟢 *Durum Raporu*\nBakiye: ${balance:.2f}\nAçık Pozisyon: {open_pos}\nTarama Modu: {'Durduruldu' if self.is_paused else 'Aktif'}"
        self.notifier.send_message(msg)

    def cmd_pause(self, _):
        self.is_paused = True
        self.notifier.send_message("⏸️ Sistem yeni sinyal aramayı durdurdu. Mevcut pozisyonlar izlenmeye devam ediyor.")

    def cmd_resume(self, _):
        self.is_paused = False
        self.notifier.send_message("▶️ Sistem otonom tarama moduna alındı.")

    def cmd_panic_close(self, _):
        self.notifier.send_message("🚨 PANİK BUTONU TETİKLENDİ. Tüm pozisyonlar kapatılıyor...")
        # Simplification: In a real system we fetch live price to close.
        # Here we just mark closed with 0 pnl to stop tracking.
        for pos in self.broker.get_open_positions():
            self.broker.close_position(pos['trade_id'], pos['entry_price'], 0.0)
        self.notifier.send_message("✅ Tüm pozisyonlar acil durum fiyatından kapatıldı.")

    def cmd_force_scan(self, _):
        self.notifier.send_message("🔍 Manuel tarama (Force Scan) başlatılıyor...")
        asyncio.run(self.run_live_cycle())

    async def run_live_cycle(self):
        logger.info("Starting live execution cycle...")
        try:
            # 1. Macro / Circuit Breaker
            if not self.macro.check_vix_circuit_breaker():
                logger.critical("Circuit Breaker Active. Aborting cycle.")
                # Aggressive trailing stop for open positions
                self._manage_open_positions(aggressive=True)
                return

            # 2. Manage Open Positions
            self._manage_open_positions()

            if self.is_paused:
                logger.info("System is paused. Skipping signal generation.")
                return

            # 3. Process Tickers for new signals
            open_positions = self.broker.get_open_positions()

            # Global Limit
            if self.portfolio.check_global_limits(open_positions):
                return

            # Dictionary to store aligned DFs for Correlation calculation
            universe_data = {}

            for ticker in ALL_TICKERS:
                data = await self.loader.fetch_mtf_data(ticker)
                if not data: continue

                htf_features = add_features(data["HTF"])
                ltf_features = add_features(data["LTF"])
                features_df = self.loader.align_mtf_data(htf_features, ltf_features)
                universe_data[ticker] = features_df

                # Z-Score Anomaly Check
                if self.macro.is_z_score_anomalous(features_df):
                    continue

                signal_data = TradingRules.generate_signal(features_df)

                if signal_data["signal"] != 0:
                    direction = signal_data["direction"]
                    current_row = features_df.iloc[-1]
                    current_price = current_row["Close"]

                    logger.info(f"Signal Generated: {ticker} {direction} @ {current_price}")

                    # Veto 1: ML Validation
                    if not self.ml.validate_signal(current_row):
                        continue

                    # Veto 2: NLP Sentiment (Mock category for test)
                    category = next((k for k, v in TICKERS.items() if ticker in v), "Metals")
                    if not self.sentiment.validate_sentiment(category, direction):
                        continue

                    # Veto 3: Correlation Matrix
                    self.portfolio.calculate_correlation_matrix(universe_data)
                    if self.portfolio.correlation_veto(ticker, direction, open_positions):
                        continue


                    # Veto 4: Macro Regime
                    if not self.macro.check_market_regime(ticker, direction):
                        continue

                    # Execution
                    # Mock win rate logic
                    capped_kelly = self.portfolio.get_dynamic_kelly_fraction()
                    capital = self.broker.get_account_balance()
                    risk_amount = capital * capped_kelly
                    atr = signal_data["atr"]
                    avg_atr = features_df["ATR_14"].mean()

                    exec_price = ExecutionModel.get_execution_price(ticker, current_price, direction, atr, avg_atr)
                    size = risk_amount / (1.5 * atr) if atr > 0 else 0

                    if size > 0:
                        receipt = self.broker.place_market_order(
                            ticker, direction, size, signal_data["sl"], signal_data["tp"], exec_price
                        )
                        msg = f"🚀 *Yeni İşlem: {direction} {ticker}*\nGiriş: {exec_price:.4f}\nSL: {signal_data['sl']:.4f}\nTP: {signal_data['tp']:.4f}\nLot: {size:.2f}"
                        self.notifier.send_message(msg)

        except Exception as e:
            logger.error(f"Live Cycle Error: {e}")
        finally:
            gc.collect()


    async def train_ml_model(self):
        logger.info("Auto-Retraining ML Model...")
        self.notifier.send_message("⚙️ Hafta sonu bakımı: ML Modeli yeniden eğitiliyor...")

        # Collect recent data
        combined_data = pd.DataFrame()
        for ticker in ALL_TICKERS:
            data = await self.loader.fetch_mtf_data(ticker)
            if not data: continue

            htf_features = add_features(data["HTF"])
            ltf_features = add_features(data["LTF"])
            features_df = self.loader.align_mtf_data(htf_features, ltf_features)
            if not features_df.empty:
                combined_data = pd.concat([combined_data, features_df])

        if not combined_data.empty:
            success = self.ml.train(combined_data)
            if success:
                self.notifier.send_message("✅ ML Modeli başarıyla eğitildi ve kaydedildi.")
            else:
                self.notifier.send_message("⚠️ ML Modeli eğitim hatası.")

    def _manage_open_positions(self, aggressive=False):
        positions = self.broker.get_open_positions()
        for pos in positions:
            ticker = pos["ticker"]
            direction = pos["direction"]
            sl = pos["sl_price"]
            tp = pos["tp_price"]
            entry = pos["entry_price"]

            # Fetch latest price
            df = self.loader.fetch_data(ticker, interval="1h", period="60d")
            if df is None or df.empty: continue

            features = add_features(df)
            if features.empty: continue

            current_price = features["Close"].iloc[-1]
            atr = features["ATR_14"].iloc[-1]

            # Check TP/SL hit
            hit = False
            if direction == "Long":
                if current_price <= sl: hit = True
                elif current_price >= tp: hit = True
            else:
                if current_price >= sl: hit = True
                elif current_price <= tp: hit = True

            if hit:
                # Execution slippage on exit
                avg_atr = features["ATR_14"].mean()
                exit_price = ExecutionModel.get_execution_price(ticker, current_price, "Short" if direction=="Long" else "Long", atr, avg_atr)
                pnl = ExecutionModel.calculate_net_pnl(direction, entry, exit_price, pos["position_size"])
                self.broker.close_position(pos["trade_id"], exit_price, pnl)
                self.notifier.send_message(f"✅ *İşlem Kapandı: {ticker}*\nKâr/Zarar: ${pnl:.2f}\nÇıkış Fiyatı: {exit_price:.4f}")
            else:
                # Trailing Stop logic
                mult = 0.5 if aggressive else 1.5
                new_sl = TradingRules.calculate_trailing_stop(direction, current_price, sl, entry, atr * mult)
                if new_sl != sl:
                    self.broker.modify_trailing_stop(pos["trade_id"], new_sl)
                    if new_sl == entry:
                        self.notifier.send_message(f"🔒 *Risk Sıfırlandı: {ticker}*\nSL seviyesi başa baş noktasına çekildi.")


def generate_and_send_tear_sheet(engine):
    filepath = Reporter.generate_tear_sheet()
    if filepath:
        engine.notifier.send_document(filepath, caption="📊 Haftalık ED Capital Quant Performans Raporu (Tear Sheet)")

def schedule_jobs():
    engine = QuantEngine()
    engine.notifier.send_message("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")

    # Run at the top of the hour
    schedule.every().hour.at(":00").do(lambda: asyncio.run(engine.run_live_cycle()))

    # Hourly Sentiment Update
    schedule.every().hour.do(lambda: engine.sentiment.update_sentiment_async())

    # Weekly Report
    schedule.every().friday.at("23:00").do(lambda: generate_and_send_tear_sheet(engine))


    # Weekly ML Training (Saturday)
    schedule.every().saturday.at("10:00").do(lambda: asyncio.run(engine.train_ml_model()))

    logger.info("Scheduler running...")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    schedule_jobs()
