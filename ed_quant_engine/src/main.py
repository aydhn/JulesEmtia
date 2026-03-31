import asyncio
import schedule
import time
from datetime import datetime
from typing import Dict, Optional, List
from src.logger import logger
from src.notifier import send_telegram_message
from src.paper_db import db
from src.data_loader import DataLoader
from src.features import add_features
from src.strategy import Strategy
from src.macro_filter import MacroFilter
from src.config import ALL_TICKERS

class QuantEngine:
    def __init__(self):
        self.tickers = ALL_TICKERS
        self.data_loader = DataLoader(self.tickers)
        self.strategy = Strategy()
        self.macro_filter = MacroFilter()
        self.state_recovered = False

    def recover_state(self):
        if not self.state_recovered:
            open_trades = db.get_open_trades()
            logger.info(f"State Recovered: Followed {len(open_trades)} open positions.")
            self.state_recovered = True

    async def process_market_data(self):
        try:
            logger.info(f"Running iteration at {datetime.now()}")
            self.recover_state()

            data = await self.data_loader.get_all_data(interval="1h", period="1y")
            regime = await self.macro_filter.get_market_regime()

            for ticker, df in data.items():
                if df.empty:
                    continue

                df = add_features(df)

                # Check Open Positions (TP/SL)
                open_trades = [t for t in db.get_open_trades() if t['ticker'] == ticker]
                for trade in open_trades:
                    current_price = df.iloc[-1]['Close']
                    exit_price = None
                    pnl = None

                    if trade['direction'] == 'Long':
                        if current_price <= trade['sl_price']:
                            exit_price = trade['sl_price']
                        elif current_price >= trade['tp_price']:
                            exit_price = trade['tp_price']
                    else:
                        if current_price >= trade['sl_price']:
                            exit_price = trade['sl_price']
                        elif current_price <= trade['tp_price']:
                            exit_price = trade['tp_price']

                    if exit_price:
                        # PNL Calculation
                        entry_price = trade['entry_price']
                        pnl_pct = (exit_price - entry_price) / entry_price if trade['direction'] == 'Long' else (entry_price - exit_price) / entry_price

                        db.close_trade(trade['trade_id'], exit_price, pnl_pct)
                        msg = f"📉 *Trade Closed*\nTicker: {ticker}\nDirection: {trade['direction']}\nEntry: {entry_price}\nExit: {exit_price}\nPNL: {pnl_pct*100:.2f}%"
                        send_telegram_message(msg)
                        logger.info(f"Closed Trade {trade['trade_id']} for {ticker} PnL: {pnl_pct*100:.2f}%")

                # Look for new signals
                signal_data = self.strategy.generate_signal(ticker, df)
                if signal_data:
                    # Macro Filter Veto
                    if not self.macro_filter.veto_signal(ticker, signal_data['direction'], regime):
                        trade_id = db.open_trade(signal_data)
                        msg = f"📈 *New Trade Opened*\nTicker: {ticker}\nDirection: {signal_data['direction']}\nEntry: {signal_data['entry_price']}\nSL: {signal_data['sl_price']}\nTP: {signal_data['tp_price']}\nSize: {signal_data['position_size']}"
                        send_telegram_message(msg)
                        logger.info(f"Opened Trade {trade_id} for {ticker}")

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            send_telegram_message(f"⚠️ *System Error*: {e}")

    def heartbeat(self):
        open_trades = len(db.get_open_trades())
        send_telegram_message(f"🟢 *System Active*\nOpen Positions: {open_trades}")

async def run_scheduler():
    engine = QuantEngine()

    # Schedule the main market check (e.g., every hour at minute 0)
    schedule.every().hour.at(":00").do(lambda: asyncio.create_task(engine.process_market_data()))

    # Daily heartbeat at 08:00
    schedule.every().day.at("08:00").do(engine.heartbeat)

    logger.info("Scheduler started.")
    send_telegram_message("🚀 *ED Capital Quant Engine Started*")

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_scheduler())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
        send_telegram_message("⏹ *System Stopped Manually*")
