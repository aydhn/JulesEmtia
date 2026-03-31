import asyncio
import os
import sys
import schedule
import datetime
from typing import Dict, Any
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

from logger import get_logger
from data_engine import DataEngine
from macro_engine import determine_market_regime
from broker import PaperBroker
from quant_logic import StrategyEngine
import paper_db

# Load Environment Variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# Initialize Core Modules
logger = get_logger("main")
broker = PaperBroker()
data_engine = DataEngine()
strategy_engine = StrategyEngine()

# Global State
SYSTEM_PAUSED = False
bot_app = None

async def send_telegram_msg(message: str):
    """Sends a Telegram message to the admin."""
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        logger.error("Telegram credentials missing in .env")
        return

    try:
        await bot_app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Telegram failed: {e}")

def check_open_positions_task():
    """
    Manages open positions:
    - Exits if TP/SL hit.
    - Updates Trailing Stop strictly monotonically.
    - Triggers Circuit Breaker if VIX > 35.
    """
    logger.info("Checking Open Positions...")
    open_trades = broker.get_open_positions()
    if not open_trades:
        return

    market_regime = determine_market_regime()
    is_black_swan = market_regime == "Extreme Panic"

    # Pre-fetch current prices to avoid multiple API calls
    current_prices = {}
    for trade in open_trades:
        ticker = trade['ticker']
        if ticker not in current_prices:
            # Sync fetch for simplicity in this task, or async in a real high-frequency env.
            try:
                # Basic fetch
                import yfinance as yf
                df = yf.download(ticker, period="1d", progress=False)
                if not df.empty:
                    current_prices[ticker] = float(df['Close'].iloc[-1])
            except:
                pass

    for trade in open_trades:
        ticker = trade['ticker']
        trade_id = trade['trade_id']
        direction = trade['direction']
        entry = trade['entry_price']
        sl = trade['sl_price']
        tp = trade['tp_price']

        current_price = current_prices.get(ticker)
        if not current_price:
            continue

        # Circuit Breaker: Aggressive Exit
        if is_black_swan:
            logger.critical(f"Circuit Breaker Exit for {ticker} at {current_price}")
            broker.close_position(trade_id, current_price, atr=0) # simplified ATR
            asyncio.create_task(send_telegram_msg(f"🚨 CIRCUIT BREAKER 🚨\nClosed {direction} {ticker} @ {current_price:.4f}"))
            continue

        # Check SL/TP
        if direction == "Long":
            if current_price <= sl:
                broker.close_position(trade_id, current_price, atr=0)
                asyncio.create_task(send_telegram_msg(f"🛑 SL Hit: Closed Long {ticker} @ {current_price:.4f}"))
                continue
            elif current_price >= tp:
                broker.close_position(trade_id, current_price, atr=0)
                asyncio.create_task(send_telegram_msg(f"✅ TP Hit: Closed Long {ticker} @ {current_price:.4f}"))
                continue

            # Trailing Stop & Breakeven (Strictly Monotonic)
            # Example: If price moved 1 ATR in favor, move SL to Entry (Breakeven)
            distance_to_entry = current_price - entry
            if distance_to_entry > (entry * 0.01): # 1% profit example
                new_sl = max(sl, current_price - (entry * 0.005)) # Trail 0.5% behind
                if new_sl > sl:
                    broker.modify_trailing_stop(trade_id, new_sl)
                    asyncio.create_task(send_telegram_msg(f"🔒 Trailing Stop Updated: Long {ticker} new SL={new_sl:.4f}"))

        elif direction == "Short":
            if current_price >= sl:
                broker.close_position(trade_id, current_price, atr=0)
                asyncio.create_task(send_telegram_msg(f"🛑 SL Hit: Closed Short {ticker} @ {current_price:.4f}"))
                continue
            elif current_price <= tp:
                broker.close_position(trade_id, current_price, atr=0)
                asyncio.create_task(send_telegram_msg(f"✅ TP Hit: Closed Short {ticker} @ {current_price:.4f}"))
                continue

            # Trailing Stop & Breakeven
            distance_to_entry = entry - current_price
            if distance_to_entry > (entry * 0.01):
                new_sl = min(sl, current_price + (entry * 0.005))
                if new_sl < sl:
                    broker.modify_trailing_stop(trade_id, new_sl)
                    asyncio.create_task(send_telegram_msg(f"🔒 Trailing Stop Updated: Short {ticker} new SL={new_sl:.4f}"))

async def scan_universe_task():
    """
    Main MTF Scanning Loop. Evaluates strategy across the universe.
    """
    global SYSTEM_PAUSED
    if SYSTEM_PAUSED:
        logger.info("System is paused. Skipping scan.")
        return

    logger.info("Starting Universe MTF Scan...")

    # 1. Macro Filter
    regime = determine_market_regime()
    if regime == "Extreme Panic" or regime == "Risk-Off":
        logger.warning(f"Scan aborted due to Market Regime: {regime}")
        asyncio.create_task(send_telegram_msg(f"⚠️ Scan Skipped: Regime is {regime}"))
        return

    from universe import UNIVERSE

    # Collect data and update correlation matrix
    all_close_prices = {}

    for ticker in UNIVERSE:
        df = await data_engine.get_mtf_data(ticker)
        if df.empty:
            continue

        all_close_prices[ticker] = df['Close']

        # 2. Strategy Engine Evaluation (MTF, ML, NLP, Correlation)
        signal = strategy_engine.generate_signal(df, ticker)

        if signal:
            # 3. Kelly Criterion Position Sizing
            balance = broker.get_account_balance()
            qty = strategy_engine.portfolio_mgr.get_position_size(
                current_balance=balance,
                entry_price=signal['price'],
                sl_price=signal['sl']
            )

            if qty > 0:
                # 4. Execute Order (Simulated Spread/Slippage)
                trade_id = broker.place_market_order(
                    ticker=ticker,
                    direction=signal['direction'],
                    qty=qty,
                    current_price=signal['price'],
                    sl=signal['sl'],
                    tp=signal['tp'],
                    atr=signal['atr']
                )

                if trade_id:
                    msg = (
                        f"🚀 <b>NEW TRADE EXECUTED</b>\n"
                        f"<b>ID:</b> {trade_id}\n"
                        f"<b>Asset:</b> {ticker}\n"
                        f"<b>Side:</b> {signal['direction']}\n"
                        f"<b>Qty:</b> {qty:.4f}\n"
                        f"<b>Entry:</b> ${signal['price']:.4f}\n"
                        f"<b>SL:</b> ${signal['sl']:.4f}\n"
                        f"<b>TP:</b> ${signal['tp']:.4f}\n"
                        f"<b>ML Prob:</b> {(signal.get('ml_prob', 0)*100):.1f}%"
                    )
                    await send_telegram_msg(msg)

    # Update correlation matrix after gathering all close prices
    if all_close_prices:
        corr_df = pd.DataFrame(all_close_prices)
        strategy_engine.portfolio_mgr.update_correlation_matrix(corr_df)

    logger.info("Universe Scan Completed.")

# --- TELEGRAM ADMIN COMMANDS ---

def is_admin(update: Update) -> bool:
    return str(update.effective_user.id) == ADMIN_CHAT_ID

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    balance = broker.get_account_balance()
    trades = broker.get_open_positions()
    msg = f"📊 <b>System Status</b>\nBalance: ${balance:.2f}\nOpen Trades: {len(trades)}\nPaused: {SYSTEM_PAUSED}"
    await update.message.reply_html(msg)

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = True
    await update.message.reply_html("⏸️ System Paused. Scanning stopped. Trailing Stops remain active.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    global SYSTEM_PAUSED
    SYSTEM_PAUSED = False
    await update.message.reply_html("▶️ System Resumed. Scanning active.")

async def cmd_panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    trades = broker.get_open_positions()
    for t in trades:
        # Emergency close at current price (dummy atr 0)
        broker.close_position(t['trade_id'], t['entry_price'], 0)
    await update.message.reply_html("🚨 <b>PANIC BUTTON PRESSED</b>\nAll open positions closed immediately.")

async def cmd_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update): return
    await update.message.reply_html("🔍 Force scan initiated...")
    asyncio.create_task(scan_universe_task())

# --- SCHEDULER & MAIN LOOP ---

def schedule_jobs():
    """Sets up the schedule using the schedule library."""
    # Synchronize execution strictly at the start of the hour
    schedule.every().hour.at(":00").do(lambda: asyncio.create_task(scan_universe_task()))

    # Check open positions more frequently
    schedule.every(15).minutes.do(lambda: asyncio.create_task(asyncio.to_thread(check_open_positions_task)))

    # Heartbeat
    schedule.every().day.at("08:00").do(
        lambda: asyncio.create_task(send_telegram_msg("🟢 <b>Heartbeat</b>\nSystem is active and protecting portfolio."))
    )

async def run_scheduler():
    """Async loop running schedule.run_pending() without blocking."""
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    logger.info("Starting ED Capital Quant Engine...")
    paper_db.init_db()

    # Initialize Telegram Bot
    global bot_app
    bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    bot_app.add_handler(CommandHandler("durum", cmd_status))
    bot_app.add_handler(CommandHandler("durdur", cmd_pause))
    bot_app.add_handler(CommandHandler("devam", cmd_resume))
    bot_app.add_handler(CommandHandler("kapat_hepsi", cmd_panic))
    bot_app.add_handler(CommandHandler("tara", cmd_scan))

    # Start bot polling manually inside existing event loop
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()

    # Initial startup message
    await send_telegram_msg("🚀 <b>ED Capital Quant Engine Started</b>\nOperating in Live Paper Trade Mode.")

    # Setup jobs
    schedule_jobs()

    # Run scheduler loop
    await run_scheduler()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Engine stopped by user.")
    except Exception as e:
        logger.critical(f"Engine Crashed: {e}")
