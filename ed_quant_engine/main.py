import asyncio
import gc
from config import INITIAL_CAPITAL, UNIVERSE, TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, VIX_PANIC_THRESHOLD, SENTIMENT_VETO_THRESHOLD
from core.paper_db import PaperDB
from core.notifier import TelegramManager
from core.logger import get_logger
from data.data_loader import DataLoader
from data.macro_filter import MacroFilter
from data.sentiment_filter import SentimentFilter
from strategy.ml_validator import MLValidator
from strategy.strategy import StrategyEngine
from execution.broker import PaperBroker
from execution.portfolio_manager import PortfolioManager
from execution.execution_model import ExecutionSimulator
from analysis.reporter import ReportEngine

logger = get_logger()

class QuantOrchestrator:
    def __init__(self):
        self.db = PaperDB()
        self.broker = PaperBroker(self.db)
        self.data_engine = DataLoader()
        self.macro_engine = MacroFilter()
        self.sentiment_engine = SentimentFilter()
        self.risk_manager = PortfolioManager(self.db)
        self.execution_simulator = ExecutionSimulator()
        self.trading_sys = StrategyEngine(self.broker)
        self.reporter = ReportEngine(self.db)
        self.ml_validator = MLValidator()
        self.telegram = TelegramManager(TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, self)

        self.capital = INITIAL_CAPITAL
        self.open_positions = []
        self.is_paused = False
        self.universe_cache = {}
        self.recover_state()

    def recover_state(self):
        self.open_positions = self.db.fetch_all("SELECT * FROM trades WHERE status = 'Open'")
        closed_pnl_tuple = self.db.fetch_all("SELECT SUM(pnl) FROM trades WHERE status = 'Closed'")
        closed_pnl = closed_pnl_tuple[0][0] if closed_pnl_tuple and closed_pnl_tuple[0][0] else 0

        self.capital = INITIAL_CAPITAL + closed_pnl
        logger.info(f"State Recovery: {len(self.open_positions)} adet açık işlem geri yüklendi. Güncel Kasa: ${self.capital:.2f}")

    async def panic_close_all(self):
        logger.critical("🚨 ACİL DURUM: Tüm pozisyonlar piyasa fiyatından kapatılıyor!")
        for trade in self.open_positions:
            t_id, ticker = trade[0], trade[1]
            try:
                # MTF async pipeline fetches
                df = self.data_engine.fetch_mtf_data(ticker)
                curr_price = df['Close'].iloc[-1]
                self.broker.close_order(t_id, curr_price)
            except Exception as e:
                logger.error(f"Panic close failure: {e}")
        self.recover_state()

    async def run_live_cycle(self):
        if self.is_paused: return

        logger.info("🟢 Canlı Tarama Döngüsü Başladı...")
        macro = self.macro_engine.get_macro_regime()

        # Circuit Breakers
        if macro['Black_Swan'] or macro['VIX'] > VIX_PANIC_THRESHOLD:
            await self.telegram.send_message(f"🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi ({macro['VIX']:.2f})! Sistem Savunma Moduna Geçti.")
            await self.panic_close_all()
            return

        current_prices = {}
        atrs = {}

        # 1. Fetch live data
        for category, tickers in UNIVERSE.items():
            for ticker in tickers:
                df = self.data_engine.fetch_mtf_data(ticker)
                if df is None or df.empty: continue

                self.universe_cache[ticker] = df
                current_prices[ticker] = df['Close'].iloc[-1]
                atrs[ticker] = df['ATR'].iloc[-1]

        # 2. Manage existing trailing stops and close hit trades
        self.trading_sys.manage_trailing_stops(self.open_positions, current_prices, atrs)
        self.recover_state()

        # 3. Hunt for new signals
        for category, tickers in UNIVERSE.items():
            for ticker in tickers:
                df = self.universe_cache.get(ticker)
                if df is None: continue

                signal = self.trading_sys.generate_signal(df)
                if signal != "Hold":

                    # 4. ML Validation Veto
                    features = [df['RSI'].iloc[-2], df['Z_Score'].iloc[-2], df['ATR'].iloc[-2]]
                    if self.ml_validator.ml_veto(features):
                        logger.info(f"{ticker} Sinyali ML Vetosu Yedi.")
                        continue

                    # 5. NLP Sentiment Veto
                    sentiment = self.sentiment_engine.get_news_sentiment("economy")
                    if (sentiment < SENTIMENT_VETO_THRESHOLD and signal == "Long") or (sentiment > abs(SENTIMENT_VETO_THRESHOLD) and signal == "Short"):
                        logger.info(f"{ticker} Sinyali NLP Haber Vetosu Yedi.")
                        continue

                    # 6. Correlation / Risk limit Veto
                    if self.risk_manager.check_correlation_veto(ticker, signal, self.universe_cache):
                        continue

                    # 7. Execution Cost Model and Sizing via Kelly
                    price = current_prices[ticker]
                    atr = atrs[ticker]
                    exec_price, cost = self.execution_simulator.get_execution_price_and_cost(category, price, atr, signal)

                    sl = exec_price - (1.5 * atr) if signal == "Long" else exec_price + (1.5 * atr)
                    tp = exec_price + (3.0 * atr) if signal == "Long" else exec_price - (3.0 * atr)

                    size = self.risk_manager.calculate_kelly_position(self.capital, exec_price, sl)

                    # 8. Fire order
                    if size > 0:
                        self.broker.place_order(ticker, signal, size, exec_price, sl, tp, cost)
                        msg = f"🚀 YENİ İŞLEM: {ticker} {signal}\nFiyat: {exec_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nLot: {size:.2f}"
                        await self.telegram.send_message(msg)
                        self.recover_state()

        self.universe_cache.clear()
        gc.collect() # Aggressive Memory Management

async def scheduler_loop(orchestrator):
    while True:
        try:
            # Run loop
            await orchestrator.run_live_cycle()
            # Then sleep for exactly one hour to align with MTF candle closures
            await asyncio.sleep(3600)
        except Exception as e:
            logger.error(f"Scheduler Hatası: {e}")
            await asyncio.sleep(60)

async def main():
    orchestrator = QuantOrchestrator()
    msg = f"🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.\nKasa: ${orchestrator.capital:.2f}\nVIX Seviyesi: İzleniyor."

    if orchestrator.telegram.app:
        await orchestrator.telegram.app.initialize()
        await orchestrator.telegram.app.start()
        await orchestrator.telegram.app.updater.start_polling()
        await orchestrator.telegram.send_message(msg)
    else:
        logger.info(msg)

    # Start loop in background async task to allow telegram polling concurrently
    asyncio.create_task(scheduler_loop(orchestrator))

    # Keep alive
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
