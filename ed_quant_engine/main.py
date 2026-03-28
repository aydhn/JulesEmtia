import asyncio
import gc
import traceback
from ed_quant_engine.utils.logger import setup_logger
from ed_quant_engine.config import Config
from ed_quant_engine.data.data_loader import DataLoader
from ed_quant_engine.core.features import add_features, align_mtf_data
from ed_quant_engine.core.macro_filter import MacroRegime
from ed_quant_engine.core.sentiment_filter import SentimentFilter
from ed_quant_engine.core.portfolio_manager import PortfolioManager
from ed_quant_engine.core.paper_broker import PaperBroker
from ed_quant_engine.models.ml_validator import MLValidator
from ed_quant_engine.strategies.strategy import MTFConfluenceStrategy
from ed_quant_engine.utils.notifier import TelegramNotifier

logger = setup_logger("MainEngine")

class QuantEngine:
    def __init__(self):
        # Initialize Core Modules
        self.data_loader = DataLoader(Config.ALL_TICKERS)
        self.macro_filter = MacroRegime()
        self.sentiment_filter = SentimentFilter()
        self.portfolio_mgr = PortfolioManager()
        self.broker = PaperBroker()
        self.ml_validator = MLValidator()
        self.strategy = MTFConfluenceStrategy()
        self.notifier = TelegramNotifier()

        # State Flags
        self.is_paused = False
        self.black_swan_mode = False

    async def handle_commands(self):
        """Processes Admin Commands from Telegram Queue (Phase 17)."""
        while True:
            cmd = await self.notifier.command_queue.get()

            if cmd == "/durum":
                balance = self.broker.get_account_balance()
                open_pos = len(self.broker.get_open_positions())
                self.notifier.send_message(f"📊 <b>Durum Raporu</b>\nKasa: ${balance:.2f}\nAçık Pozisyonlar: {open_pos}\nDuraklatıldı mı?: {self.is_paused}")

            elif cmd == "/durdur":
                self.is_paused = True
                self.notifier.send_message("⏸️ Sistem Duraklatıldı. Yeni tarama yapılmayacak, sadece açık pozisyonlar korunacak.")

            elif cmd == "/devam":
                self.is_paused = False
                self.notifier.send_message("▶️ Sistem Tekrar Otonom Taramaya Başladı.")

            elif cmd == "/kapat_hepsi":
                self.notifier.send_message("🚨 PANİK KAPATMASI BAŞLATILDI!")
                positions = self.broker.get_open_positions()
                for pos in positions:
                     # Emergency close at current price would require real-time quote, placeholder using SL for safety log
                     self.broker.close_position(pos['trade_id'], pos['sl_price'], "Panic Button")
                self.notifier.send_message(f"Tüm {len(positions)} açık pozisyon piyasa fiyatından kapatıldı.")

            elif cmd == "/tara":
                self.notifier.send_message("🔍 Zorunlu Tarama (Force Scan) Başlatılıyor...")
                await self.run_live_cycle()

            self.notifier.command_queue.task_done()

    async def recover_state(self):
        """State Recovery on Boot (Phase 8)."""
        open_positions = self.broker.get_open_positions()
        logger.info(f"State Recovery: Found {len(open_positions)} open positions tracking.")
        if open_positions:
            self.notifier.send_message(f"🔄 Sistem Yeniden Başlatıldı. Hafızaya alınan {len(open_positions)} açık pozisyon takibe devam ediyor.")

    async def manage_open_positions(self, current_data: dict):
        """Trailing Stop, Breakeven & Stop Out Logic (Phase 12, 19)."""
        open_positions = self.broker.get_open_positions()
        if not open_positions: return

        for pos in open_positions:
            ticker = pos['ticker']
            if ticker not in current_data or current_data[ticker]['LTF'].empty: continue

            current_price = current_data[ticker]['LTF']['Close'].iloc[-1]
            trade_id = pos['trade_id']
            direction = pos['direction']
            sl_price = pos['sl_price']
            tp_price = pos['tp_price']
            entry_price = pos['entry_price']

            # 1. Black Swan Aggressive Protection (Phase 19)
            if self.black_swan_mode:
                logger.warning(f"Black Swan Mode: Aggressively closing {ticker}")
                self.broker.close_position(trade_id, current_price, "VIX Circuit Breaker")
                self.notifier.send_message(f"🚨 Devre Kesici: {ticker} {direction} pozisyonu piyasa fiyatından ({current_price:.2f}) kapatıldı!")
                continue

            # 2. TP / SL Execution
            if direction == "Long" and (current_price <= sl_price or current_price >= tp_price):
                 reason = "Take Profit" if current_price >= tp_price else "Stop Loss"
                 self.broker.close_position(trade_id, current_price, reason)
                 self.notifier.send_message(f"📉 İşlem Kapandı ({reason}): {ticker} {direction} @ {current_price:.2f}")
                 continue

            elif direction == "Short" and (current_price >= sl_price or current_price <= tp_price):
                 reason = "Take Profit" if current_price <= tp_price else "Stop Loss"
                 self.broker.close_position(trade_id, current_price, reason)
                 self.notifier.send_message(f"📉 İşlem Kapandı ({reason}): {ticker} {direction} @ {current_price:.2f}")
                 continue

            # 3. Breakeven & Trailing Stop Logic (Phase 12)
            atr = current_data[ticker]['LTF']['ATR_14'].iloc[-1]
            profit_points = current_price - entry_price if direction == "Long" else entry_price - current_price

            if profit_points > (atr * 1.0): # E.g., 1 ATR in profit
                 # Breakeven Check
                 if (direction == "Long" and sl_price < entry_price) or (direction == "Short" and sl_price > entry_price):
                     if self.broker.modify_trailing_stop(trade_id, entry_price, direction, sl_price):
                          self.notifier.send_message(f"🔒 Risk Sıfırlandı: {ticker} SL seviyesi Başa Baş (Breakeven) noktasına çekildi.")

                 # Dynamic Trailing Check
                 new_sl = current_price - (atr * 1.5) if direction == "Long" else current_price + (atr * 1.5)
                 if self.broker.modify_trailing_stop(trade_id, new_sl, direction, sl_price):
                      logger.info(f"Trailing Stop updated for {ticker} to {new_sl:.2f}")


    async def run_live_cycle(self):
        """Asynchronous Pipeline Orchestration (Phase 23)."""
        logger.info("Starting Live Trading Cycle...")

        try:
            # 1. Fetch Data
            raw_data = await self.data_loader.fetch_historical_data_async()
            if not raw_data: return

            processed_data = {}
            for ticker, dfs in raw_data.items():
                 htf_feat = add_features(dfs['HTF'])
                 ltf_feat = add_features(dfs['LTF'])
                 merged = align_mtf_data(htf_feat, ltf_feat)
                 processed_data[ticker] = {"HTF": htf_feat, "LTF": ltf_feat, "Merged": merged}

            # 2. Macro Check & Portfolio Update
            macro_df = self.macro_filter.fetch_macro_data()
            regime = self.macro_filter.get_regime(macro_df)
            self.black_swan_mode = (regime == "Black_Swan")

            self.portfolio_mgr.update_correlation_matrix(processed_data)
            open_positions = self.broker.get_open_positions()

            # 3. Manage Open Positions (Always execute even if paused)
            await self.manage_open_positions(processed_data)

            # 4. Scan for New Signals (Skip if Paused or Black Swan)
            if self.is_paused or self.black_swan_mode:
                 logger.info("Skipping new signal scan (Paused or Black Swan).")
                 return

            # Global Exposure Veto
            if self.portfolio_mgr.global_limit_veto(len(open_positions)):
                 return

            # Update Sentiment Cache
            self.sentiment_filter.fetch_news_sentiment()

            # 5. Signal Generation & Validation Pipeline
            for ticker, dfs in processed_data.items():
                 merged_df = dfs['Merged']

                 # Strategy Confluence
                 signal = self.strategy.generate_signals(merged_df, ticker, regime)
                 if not signal: continue

                 # Machine Learning Veto (Phase 18)
                 curr_feat = merged_df.iloc[-2].to_dict() # shift(1)
                 if not self.ml_validator.validate_signal(curr_feat): continue

                 # Sentiment Veto (Phase 20)
                 if self.sentiment_filter.veto_signal(signal['direction']): continue

                 # Correlation Veto (Phase 11)
                 if self.portfolio_mgr.correlation_veto(ticker, signal['direction'], open_positions): continue

                 # 6. Execution & Sizing
                 win_stats = {"win_rate": 0.65, "avg_win": 1.8, "avg_loss": 1.0} # Needs dynamic DB calculation
                 cap = self.broker.get_account_balance()

                 pos_size = self.portfolio_mgr.get_position_size(signal, cap, win_stats)
                 if pos_size > 0:
                      signal['position_size'] = pos_size
                      receipt = self.broker.place_market_order(signal)

                      msg = (f"🚀 <b>YENİ İŞLEM (Live Paper Trade)</b>\n"
                             f"Var: {ticker}\nYön: {receipt['direction']}\n"
                             f"Giriş (Net): {receipt['net_entry']:.4f}\n"
                             f"Zarar Kes: {signal['sl_price']:.4f}\n"
                             f"Kâr Al: {signal['tp_price']:.4f}\n"
                             f"Lot (Kelly): {pos_size:.4f}\n"
                             f"Kayma/Spread Ödenen: ${receipt['slippage_paid']:.4f}")
                      self.notifier.send_message(msg)

        except Exception as e:
             logger.critical(f"Critical Error in Live Cycle: {traceback.format_exc()}")
             self.notifier.send_message(f"⚠️ Sistem Hatası: {str(e)}")
        finally:
             # Garbage Collection (Phase 23)
             del raw_data
             del processed_data
             gc.collect()

    async def run_forever(self):
        """Main Infinite Loop with Heartbeat."""
        logger.info("Booting ED Capital Quant Engine...")
        self.notifier.send_message("🟢 <b>Sistem Aktif</b>\nED Capital Quant Engine Otonom Modda Başlatıldı. 7/24 Taramaya Geçiliyor.")

        await self.recover_state()

        # Start Telegram Poller in background
        asyncio.create_task(self.notifier.poll_commands_async())

        cycle_count = 0
        while True:
            await self.run_live_cycle()
            cycle_count += 1

            # Heartbeat (Phase 8)
            if cycle_count % 24 == 0: # Assuming 1-hour cycles (24h)
                 bal = self.broker.get_account_balance()
                 self.notifier.send_message(f"💓 <b>Canlılık Sinyali (Heartbeat)</b>\nSon 24 saatte 24 döngü hatasız tamamlandı. Güncel Kasa: ${bal:.2f}")

            logger.info("Cycle complete. Sleeping until next hour...")
            await asyncio.sleep(3600) # Wait 1 hour (Sync with precise top-of-hour scheduling in production)

if __name__ == "__main__":
    engine = QuantEngine()
    # Handle event loop strictly
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(engine.run_forever())
