"""
ED Capital Quant Engine - Main Orchestrator Loop
Asynchronous, fault-tolerant execution engine.
"""
import asyncio
import time
from datetime import datetime
from core.logger import logger
from core.notifier import notify_admin
from core.config import UNIVERSE
from core.data_loader import data_loader
from core.paper_db import db
from features.indicators import add_features
from strategy.signals import generate_signals

async def check_open_positions(current_prices: dict):
    """Monitor open trades for TP/SL hits and Trailing SL adjustments."""
    open_trades = db.get_open_trades()
    for trade in open_trades:
        ticker = trade['ticker']
        if ticker not in current_prices:
            continue

        current_price = current_prices[ticker]
        direction = trade['direction']
        sl = trade['sl_price']
        tp = trade['tp_price']
        entry = trade['entry_price']
        size = trade['position_size']
        trade_id = trade['trade_id']

        # Determine if closed
        closed = False
        pnl = 0.0

        if direction == 'Long':
            if current_price <= sl: # Hit SL
                closed = True
                pnl = (sl - entry) * size
            elif current_price >= tp: # Hit TP
                closed = True
                pnl = (tp - entry) * size
        else: # Short
            if current_price >= sl: # Hit SL
                closed = True
                pnl = (entry - sl) * size
            elif current_price <= tp: # Hit TP
                closed = True
                pnl = (entry - tp) * size

        if closed:
            exit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.close_trade(trade_id, exit_time, current_price, pnl)
            notify_admin(f"🔒 Trade Closed: {ticker} {direction} | PnL: ${pnl:.2f} | Exit: {current_price}")
        else:
            # Check Trailing Stop logic (simplified Phase 12 preview)
            pass

async def live_cycle():
    """One full cycle of data fetching, processing, monitoring, and executing."""
    logger.info("Starting live cycle...")

    # Flatten universe for easy iteration
    flat_tickers = [ticker for group in UNIVERSE.values() for ticker in group]

    # 1. Fetch current data
    data_dict = await data_loader.fetch_universe_async(UNIVERSE, period="100d", interval="1d")
    current_prices = {ticker: df['Close'].iloc[-1] for ticker, df in data_dict.items() if not df.empty}

    # 2. Check open positions
    await check_open_positions(current_prices)

    # 3. Scan for new signals
    for ticker, df in data_dict.items():
        if df.empty:
            continue

        # Add technical features
        features_df = add_features(df)

        if features_df.empty:
            continue

        # Check strategy rules
        signal_data = generate_signals(features_df, ticker)

        if signal_data:
            # Fake Macro/Correlation/ML veto checks would go here...
            # For now, if signal exists, enter trade
            entry_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            trade_id = db.open_trade(
                ticker=ticker,
                direction=signal_data['direction'],
                entry_time=entry_time,
                entry_price=signal_data['entry_price'],
                sl_price=signal_data['sl_price'],
                tp_price=signal_data['tp_price'],
                position_size=signal_data['position_size']
            )

            if trade_id:
                notify_admin(f"✅ New Trade: {ticker} {signal_data['direction']}\nEntry: {signal_data['entry_price']}\nSL: {signal_data['sl_price']}\nTP: {signal_data['tp_price']}\nSize: {signal_data['position_size']}")

    logger.info("Live cycle completed.")

async def main_loop():
    """Infinite loop orchestrating the bot."""
    notify_admin("🚀 ED Capital Quant Engine Started.")

    while True:
        try:
            await live_cycle()
            # Wait 1 hour (3600 seconds) before next scan. Adjust for testing.
            await asyncio.sleep(3600)
        except Exception as e:
            logger.critical(f"Main loop crashed: {e}")
            await asyncio.sleep(60) # Wait 1 minute before retrying on failure

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("Bot manually stopped.")
        notify_admin("🛑 ED Capital Quant Engine Manually Stopped.")
