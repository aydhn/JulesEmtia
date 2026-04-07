import asyncio
import schedule
import time
from datetime import datetime
import gc
from src.logger import logger
from src.notifier import send_telegram_message
from src.data_loader import DataLoader
from src.features import add_features
from src.strategy import Strategy
from src.macro_filter import MacroFilter
from src.portfolio_manager import PortfolioManager
from src.trailing_stop import TrailingStopManager
from src.ml_validator import MLValidator
from src.circuit_breaker import CircuitBreaker
from src.sentiment_filter import SentimentFilter
from src.execution_model import ExecutionModel
from src.kelly_criterion import KellyCalculator
from src.abstract_broker import PaperBroker
from src.config import ALL_TICKERS
from src.paper_db import db

class LiveQuantEngine:
    def __init__(self):
        self.tickers = ALL_TICKERS
        self.data_loader = DataLoader(self.tickers)
        self.strategy = Strategy()
        self.macro_filter = MacroFilter()
        self.portfolio_manager = PortfolioManager()
        self.trailing_stop_manager = TrailingStopManager()
        self.ml_validator = MLValidator()
        self.circuit_breaker = CircuitBreaker()
        self.sentiment_filter = SentimentFilter()
        self.execution_model = ExecutionModel()
        self.kelly_calculator = KellyCalculator()
        self.broker = PaperBroker()

        self.state_recovered = False
        self.is_paused = False

    def recover_state(self):
        if not self.state_recovered:
            open_trades = self.broker.get_open_positions()
            logger.info(f"State Recovered: Followed {len(open_trades)} open positions.")
            self.state_recovered = True

    async def _manage_open_positions(self, data, is_black_swan):
        open_trades = self.broker.get_open_positions()
        for trade in open_trades:
            ticker = trade['ticker']
            df = data.get(ticker)
            if df is None or df.empty: continue

            df = add_features(df)
            current_price = df['Close'].iloc[-1]
            atr = df['ATR_14'].iloc[-1]
            avg_atr = df['ATR_14'].rolling(50).mean().iloc[-1]

            exit_price = None
            direction = trade['direction']

            # Defense Mode Check
            if is_black_swan:
                logger.warning(f"Defense Mode active for {ticker}.")
                new_aggressive_sl = self.circuit_breaker.activate_defense_mode(current_price, trade, atr)
                self.broker.modify_trailing_stop(trade['trade_id'], new_aggressive_sl)
                # Ensure local object is updated for next checks
                trade['sl_price'] = new_aggressive_sl

            # TP / SL Checks
            if direction == 'Long':
                if current_price <= trade['sl_price']:
                    exit_price = self.execution_model.apply_exit_costs(ticker, direction, trade['sl_price'], atr, avg_atr)
                elif current_price >= trade['tp_price']:
                    exit_price = self.execution_model.apply_exit_costs(ticker, direction, trade['tp_price'], atr, avg_atr)
            else:
                if current_price >= trade['sl_price']:
                    exit_price = self.execution_model.apply_exit_costs(ticker, direction, trade['sl_price'], atr, avg_atr)
                elif current_price <= trade['tp_price']:
                    exit_price = self.execution_model.apply_exit_costs(ticker, direction, trade['tp_price'], atr, avg_atr)

            if exit_price:
                # Close Position
                entry_price = trade['entry_price']
                pnl_pct = (exit_price - entry_price) / entry_price if direction == 'Long' else (entry_price - exit_price) / entry_price

                self.broker.close_position(trade['trade_id'], exit_price, pnl_pct)
                msg = f"📉 *Trade Closed*\nTicker: {ticker}\nDirection: {direction}\nEntry: {entry_price:.4f}\nExit: {exit_price:.4f}\nPNL: {pnl_pct*100:.2f}%"
                send_telegram_message(msg)
                logger.info(f"Closed {trade['trade_id']} for {ticker} PnL: {pnl_pct*100:.2f}%")
            else:
                # Trailing Stop Management
                self.trailing_stop_manager.manage_trailing_stop(current_price, atr, trade)

    async def retrain_ml_model(self):
        logger.info("Starting scheduled ML model retraining...")
        send_telegram_message("🤖 *ML Training Started*: Fetching recent historical data for Random Forest optimization.")
        try:
            data = await self.data_loader.get_all_data(interval="1d", period="2y")
            await asyncio.to_thread(self.ml_validator.train_model, data)
            send_telegram_message("✅ *ML Training Complete*: The model has been successfully retrained and saved.")
        except Exception as e:
            logger.error(f"Error during ML retraining: {e}")
            send_telegram_message(f"⚠️ *ML Training Error*: {e}")

    async def run_live_cycle(self):
        try:
            logger.info(f"Starting Live Cycle at {datetime.now()}")
            self.recover_state()

            # 1. Data Fetching
            data_1h = await self.data_loader.get_all_data(interval="1h", period="1y")
            data_1d = await self.data_loader.get_all_data(interval="1d", period="1y")
            regime = await self.macro_filter.get_market_regime()

            # 2. Black Swan Check
            is_black_swan = await self.circuit_breaker.check_black_swan()

            # 3. Position Management (Always runs, even if paused or black swan)
            await self._manage_open_positions(data_1h, is_black_swan)

            if self.is_paused or is_black_swan:
                logger.info("System is paused or in defense mode. Skipping new signals.")
                return

            # 4. Filter & Signal Generation
            corr_matrix = self.portfolio_manager.calculate_correlation_matrix(data_1d)
            current_capital = self.broker.get_account_balance()
            kelly_fraction = self.kelly_calculator.get_fractional_kelly()

            for ticker, df_1h in data_1h.items():
                if df_1h.empty: continue

                # Z-Score Flash Crash Anomaly Detection
                if self.circuit_breaker.check_flash_crash(ticker, df_1h):
                     continue # Halt trading for this ticker

                df_1h = add_features(df_1h)
                df_1d = data_1d.get(ticker)
                if df_1d is not None and not df_1d.empty:
                    df_1d = add_features(df_1d)

                signal_data = self.strategy.generate_signal(ticker, df_1h)

                if signal_data:
                    direction = signal_data['direction']

                    # MTF Confirmation (Daily Trend Master Veto)
                    if df_1d is not None and not df_1d.empty:
                        last_daily_close = df_1d.iloc[-2]['Close'] # Shift(1) daily for safety
                        daily_ema_50 = df_1d.iloc[-2]['EMA_50']
                        daily_macd_hist = df_1d.iloc[-2]['MACD_Hist']

                        mtf_veto = False
                        if direction == "Long" and (last_daily_close < daily_ema_50 or daily_macd_hist < 0):
                            mtf_veto = True
                        elif direction == "Short" and (last_daily_close > daily_ema_50 or daily_macd_hist > 0):
                            mtf_veto = True

                        if mtf_veto:
                             logger.info(f"MTF Veto: {direction} on {ticker} rejected due to Daily Trend.")
                             continue

                    # Macro Veto
                    if self.macro_filter.veto_signal(ticker, direction, regime): continue

                    # Sentiment Veto
                    if self.sentiment_filter.veto_signal(ticker, direction): continue

                    # ML Validation
                    # Use last row features from 1H
                    current_features = df_1h.iloc[-1][['EMA_50', 'EMA_200', 'RSI_14', 'MACD', 'MACD_Hist', 'ATR_14', 'Log_Return']].to_dict()
                    if not self.ml_validator.validate_signal(current_features): continue

                    # Correlation Veto
                    if self.portfolio_manager.veto_correlation(ticker, direction, corr_matrix): continue

                    # Global Limit Veto
                    if self.portfolio_manager.veto_global_limits(current_capital, kelly_fraction): continue

                    # 5. Execution
                    market_price = df_1h.iloc[-1]['Close']
                    current_atr = df_1h.iloc[-1]['ATR_14']
                    avg_atr = df_1h['ATR_14'].rolling(50).mean().iloc[-1]

                    entry_price = self.execution_model.apply_entry_costs(ticker, direction, market_price, current_atr, avg_atr)

                    # Recalculate size with entry price using Kelly
                    risk_amount = current_capital * kelly_fraction
                    sl_distance = abs(entry_price - signal_data['sl_price'])
                    size = risk_amount / sl_distance if sl_distance > 0 else 0

                    if size > 0:
                        trade_id = self.broker.place_market_order(
                            ticker, direction, size, entry_price, signal_data['sl_price'], signal_data['tp_price']
                        )

                        msg = (f"📈 *New Trade Executed*\nTicker: {ticker}\nDirection: {direction}\n"
                               f"Entry: {entry_price:.4f} (Mkt: {market_price:.4f})\n"
                               f"SL: {signal_data['sl_price']:.4f}\nTP: {signal_data['tp_price']:.4f}\nSize: {size:.4f}")
                        send_telegram_message(msg)
                        logger.info(f"Executed Trade {trade_id} for {ticker}")

        except Exception as e:
            logger.error(f"Error in Live Cycle: {e}", exc_info=True)
            send_telegram_message(f"⚠️ *System Error*: {e}")
        finally:
            # Garbage Collection
            del data_1h
            del data_1d
            gc.collect()

    async def handle_telegram_command(self, update, context):
        text = update.message.text
        chat_id = str(update.message.chat_id)
        from src.config import ADMIN_CHAT_ID

        if chat_id != str(ADMIN_CHAT_ID):
            logger.critical(f"Unauthorized access attempt from Chat ID: {chat_id}")
            return

        if text == "/durum":
             balance = self.broker.get_account_balance()
             open_trades = len(self.broker.get_open_positions())
             await update.message.reply_text(f"📊 *Status*\nBalance: ${balance:.2f}\nOpen Positions: {open_trades}", parse_mode='Markdown')
        elif text == "/durdur":
             self.is_paused = True
             await update.message.reply_text("⏸ *System Paused*. Managing open positions only.")
        elif text == "/devam":
             self.is_paused = False
             await update.message.reply_text("▶️ *System Resumed*.")
        elif text == "/kapat_hepsi":
             open_trades = self.broker.get_open_positions()
             for t in open_trades:
                 self.broker.close_position(t['trade_id'], t['entry_price'], 0) # Panic close at entry
             await update.message.reply_text("🚨 *PANIC CLOSE EXECUTED*.")

async def start_bot():
    engine = LiveQuantEngine()

    # Precise Top of Hour Scheduling
    schedule.every().hour.at(":00").do(lambda: asyncio.create_task(engine.run_live_cycle()))

    # Tear Sheet Generation
    from src.reporter import TearSheetReporter
    reporter = TearSheetReporter()
    schedule.every().friday.at("22:00").do(lambda: reporter.generate_report())

    # Schedule ML Retraining (Every Saturday at 12:00)
    schedule.every().saturday.at("12:00").do(lambda: asyncio.create_task(engine.retrain_ml_model()))

    # Try an initial ML training if the model doesn't exist yet
    if engine.ml_validator.model is None:
         logger.info("No ML model found on startup. Triggering initial training...")
         asyncio.create_task(engine.retrain_ml_model())

    send_telegram_message("🚀 *ED Capital Quant Engine Live Mode Started*\nSyncing with market data...")
    logger.info("ED Capital Engine Started.")

    # Telegram Bot Polling Setup
    from telegram.ext import Application, CommandHandler
    from src.config import TELEGRAM_BOT_TOKEN

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("durum", engine.handle_telegram_command))
    application.add_handler(CommandHandler("durdur", engine.handle_telegram_command))
    application.add_handler(CommandHandler("devam", engine.handle_telegram_command))
    application.add_handler(CommandHandler("kapat_hepsi", engine.handle_telegram_command))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
