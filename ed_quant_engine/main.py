import asyncio
import gc
from config import INITIAL_CAPITAL, UNIVERSE, TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, VIX_PANIC_THRESHOLD
from core_engine import PaperDB, TelegramManager, logger
from data_intelligence import DataEngine
from risk_portfolio import RiskManager
from trading_logic import PaperBroker, TradingSystem
from reporter import ReportEngine

# Phase 5, 23: Main Orchestration & Live Cycle
class QuantOrchestrator:
    def __init__(self):
        self.db = PaperDB()
        self.broker = PaperBroker(self.db)
        self.data_engine = DataEngine()
        self.risk_manager = RiskManager(self.db)
        self.trading_sys = TradingSystem(self.broker)
        self.reporter = ReportEngine(self.db)

        self.telegram = TelegramManager(TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, self)

        self.capital = INITIAL_CAPITAL
        self.open_positions = []
        self.is_paused = False
        self.universe_cache = {}
        self.recover_state()

    def recover_state(self):
        self.open_positions = self.db.fetch_all("SELECT * FROM trades WHERE status = 'Open'")
        closed_pnl = self.db.fetch_all("SELECT SUM(pnl) FROM trades WHERE status = 'Closed'")[0][0]
        self.capital = INITIAL_CAPITAL + (closed_pnl if closed_pnl else 0)
        logger.info(f"State Recovery: {len(self.open_positions)} adet açık işlem geri yüklendi. Güncel Kasa: ${self.capital:.2f}")

    async def panic_close_all(self):
        logger.critical("🚨 ACİL DURUM: Tüm pozisyonlar piyasa fiyatından kapatılıyor!")
        for trade in self.open_positions:
            t_id, ticker = trade[0], trade[1]
            try:
                curr_price = self.data_engine.fetch_mtf_data(ticker)['Close'].iloc[-1]
                self.broker.close_order(t_id, curr_price)
            except: pass
        self.recover_state()

    async def run_live_cycle(self):
        if self.is_paused: return

        logger.info("🟢 Canlı Tarama Döngüsü Başladı...")
        macro = self.data_engine.get_macro_regime()

        if macro['Black_Swan'] or macro['VIX'] > VIX_PANIC_THRESHOLD:
            await self.telegram.send_message(f"🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi ({macro['VIX']:.2f})! Sistem Savunma Moduna Geçti.")
            await self.panic_close_all()
            return

        current_prices = {}
        atrs = {}

        for category, tickers in UNIVERSE.items():
            for ticker in tickers:
                df = self.data_engine.fetch_mtf_data(ticker)
                if df is None or df.empty: continue

                self.universe_cache[ticker] = df
                current_prices[ticker] = df['Close'].iloc[-1]
                atrs[ticker] = df['ATR'].iloc[-1]

        self.trading_sys.manage_trailing_stops(self.open_positions, current_prices, atrs)
        self.recover_state()

        for category, tickers in UNIVERSE.items():
            for ticker in tickers:
                df = self.universe_cache.get(ticker)
                if df is None: continue

                signal = self.trading_sys.generate_signal(df)
                if signal != "Hold":

                    features = [df['RSI'].iloc[-2], df['Z_Score'].iloc[-2], df['ATR'].iloc[-2]]
                    if self.data_engine.ml_veto(features):
                        logger.info(f"{ticker} Sinyali ML Vetosu Yedi.")
                        continue

                    sentiment = self.data_engine.get_news_sentiment("economy")
                    if (sentiment < -0.5 and signal == "Long") or (sentiment > 0.5 and signal == "Short"):
                        logger.info(f"{ticker} Sinyali NLP Haber Vetosu Yedi.")
                        continue

                    if self.risk_manager.check_correlation_veto(ticker, signal, self.universe_cache):
                        continue

                    # Execution
                    price = current_prices[ticker]
                    atr = atrs[ticker]
                    exec_price, cost = self.risk_manager.execution_simulator(category, price, atr, signal)

                    sl = exec_price - (1.5 * atr) if signal == "Long" else exec_price + (1.5 * atr)
                    tp = exec_price + (3.0 * atr) if signal == "Long" else exec_price - (3.0 * atr)

                    size = self.risk_manager.calculate_kelly_position(self.capital, exec_price, sl)

                    if size > 0:
                        self.broker.place_order(ticker, signal, size, exec_price, sl, tp, cost)
                        msg = f"🚀 YENİ İŞLEM: {ticker} {signal}\nFiyat: {exec_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nLot: {size:.2f}"
                        await self.telegram.send_message(msg)
                        self.recover_state()

        self.universe_cache.clear()
        gc.collect()

async def scheduler_loop(orchestrator):
    while True:
        try:
            await orchestrator.run_live_cycle()
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

    await scheduler_loop(orchestrator)

if __name__ == "__main__":
    asyncio.run(main())
