import asyncio
import schedule
import time
from datetime import datetime
import gc
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from data_loader import DataLoader
from features import add_features
from macro_filter import MacroRegimeFilter
from strategy import QuantStrategy
from portfolio_manager import PortfolioManager
from execution_model import ExecutionSimulator
from ml_validator import MLValidator
from sentiment_filter import SentimentFilter
from broker import PaperBroker
from reporter import TearSheetReporter
from notifier import async_send_telegram_message, TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from paper_db import PaperDB
from logger import logger

# Initialize Broker (Abstraction Layer)
broker = PaperBroker()

# Global State Flags (Manual Override)
is_paused = False

async def manage_open_positions(universe_data: dict, macro_df: pd.DataFrame):
    """Phase 12, 19: Trade Management."""
    global broker
    open_trades = broker.get_open_positions()
    if not open_trades:
        return

    vix_tripped = MacroRegimeFilter.check_vix_circuit_breaker(macro_df)

    for trade in open_trades:
        trade_id = trade['trade_id']
        ticker = trade['ticker']
        direction = trade['direction']
        entry_price = trade['entry_price']
        current_sl = trade['sl_price']

        if ticker not in universe_data or universe_data[ticker][1] is None or universe_data[ticker][1].empty:
            continue

        hourly_df = universe_data[ticker][1]
        latest_price = hourly_df.iloc[-1]['Close']
        current_atr = hourly_df.iloc[-1]['ATR_14']

        # 1. Black Swan Protection
        if vix_tripped:
            logger.critical(f"Circuit Breaker: Panic closing {ticker} at {latest_price}")
            exit_price = ExecutionSimulator.execute_trade_price(ticker, latest_price, -1 if direction == "Long" else 1, pd.Series([current_atr]))
            receipt = broker.close_position(trade_id, exit_price, reason="VIX_CIRCUIT_BREAKER")
            await async_send_telegram_message(f"🚨 <b>VIX PANIC CLOSE</b>\n{ticker} closed at {exit_price:.2f}\nPnL: {receipt.get('realized_pnl', 0):.2f}")
            continue

        # 2. SL / TP Check
        if direction == "Long":
            if latest_price <= current_sl:
                exit_price = ExecutionSimulator.execute_trade_price(ticker, current_sl, -1, pd.Series([current_atr]))
                receipt = broker.close_position(trade_id, exit_price, reason="SL_HIT")
                await async_send_telegram_message(f"❌ <b>STOP LOSS HIT</b>\n{ticker} Long closed at {exit_price:.2f}\nPnL: {receipt.get('realized_pnl', 0):.2f}")
                continue
            elif latest_price >= trade['tp_price']:
                exit_price = ExecutionSimulator.execute_trade_price(ticker, trade['tp_price'], -1, pd.Series([current_atr]))
                receipt = broker.close_position(trade_id, exit_price, reason="TP_HIT")
                await async_send_telegram_message(f"✅ <b>TAKE PROFIT HIT</b>\n{ticker} Long closed at {exit_price:.2f}\nPnL: {receipt.get('realized_pnl', 0):.2f}")
                continue

            profit_dist = latest_price - entry_price
            if profit_dist > current_atr:
                new_sl = latest_price - (1.5 * current_atr)
                if new_sl > current_sl:
                    if broker.modify_trailing_stop(trade_id, new_sl):
                        await async_send_telegram_message(f"🔒 <b>TRAILING STOP UPDATED</b>\n{ticker} Long SL moved to {new_sl:.2f}")

        elif direction == "Short":
            if latest_price >= current_sl:
                exit_price = ExecutionSimulator.execute_trade_price(ticker, current_sl, 1, pd.Series([current_atr]))
                receipt = broker.close_position(trade_id, exit_price, reason="SL_HIT")
                await async_send_telegram_message(f"❌ <b>STOP LOSS HIT</b>\n{ticker} Short closed at {exit_price:.2f}\nPnL: {receipt.get('realized_pnl', 0):.2f}")
                continue
            elif latest_price <= trade['tp_price']:
                exit_price = ExecutionSimulator.execute_trade_price(ticker, trade['tp_price'], 1, pd.Series([current_atr]))
                receipt = broker.close_position(trade_id, exit_price, reason="TP_HIT")
                await async_send_telegram_message(f"✅ <b>TAKE PROFIT HIT</b>\n{ticker} Short closed at {exit_price:.2f}\nPnL: {receipt.get('realized_pnl', 0):.2f}")
                continue

            profit_dist = entry_price - latest_price
            if profit_dist > current_atr:
                new_sl = latest_price + (1.5 * current_atr)
                if new_sl < current_sl:
                    if broker.modify_trailing_stop(trade_id, new_sl):
                        await async_send_telegram_message(f"🔒 <b>TRAILING STOP UPDATED</b>\n{ticker} Short SL moved to {new_sl:.2f}")

async def run_live_cycle():
    """Phase 23: Live Forward Paper Trading Pipeline."""
    global is_paused
    logger.info("Starting live scan cycle...")

    try:
        universe_raw = await DataLoader.get_all_universe_data()
        macro_df = await MacroRegimeFilter.fetch_macro_data()

        universe_data = {}
        for ticker, (daily, hourly) in universe_raw.items():
            try:
                d_feat = add_features(daily, "1d")
                h_feat = add_features(hourly, "1h")
                universe_data[ticker] = (d_feat, h_feat)
            except Exception as e:
                logger.error(f"Error processing features for {ticker}: {e}")

        await manage_open_positions(universe_data, macro_df)

        if is_paused:
            logger.info("System is paused. Skipping new signal generation.")
            return

        if MacroRegimeFilter.check_vix_circuit_breaker(macro_df):
            return

        if MacroRegimeFilter.is_risk_off(macro_df):
            logger.warning("Risk-Off Regime active. Proceeding with caution.")

        corr_matrix = await PortfolioManager.calculate_correlation_matrix({k: v[0] for k, v in universe_data.items()})

        for ticker, (daily_df, hourly_df) in universe_data.items():
            signal = await QuantStrategy.generate_signal(ticker, hourly_df, daily_df, corr_matrix)

            if signal:
                bal = broker.get_account_balance()
                risk_amt, pos_size = PortfolioManager.calculate_position_size(bal, signal['entry_price'], signal['sl_price'])

                if pos_size > 0:
                    receipt = broker.place_market_order(
                        ticker=signal['ticker'],
                        direction=signal['direction'],
                        position_size=pos_size,
                        entry_price=signal['entry_price'],
                        sl_price=signal['sl_price'],
                        tp_price=signal['tp_price'],
                        reason=f"MTF_Signal_Prob_{signal['prob']:.2f}"
                    )

                    msg = (
                        f"🚀 <b>NEW TRADE OPENED</b>\n"
                        f"Asset: {signal['ticker']}\n"
                        f"Dir: {signal['direction']}\n"
                        f"Entry: {signal['entry_price']:.4f}\n"
                        f"SL: {signal['sl_price']:.4f}\n"
                        f"TP: {signal['tp_price']:.4f}\n"
                        f"Size: {pos_size:.4f} units\n"
                        f"Risk: ${risk_amt:.2f} (Kelly)\n"
                        f"ML Prob: {signal['prob']:.0%}"
                    )
                    await async_send_telegram_message(msg)

    except Exception as e:
        logger.error(f"Error in live cycle: {e}")
        await async_send_telegram_message(f"⚠️ <b>SYSTEM ERROR</b>\nLive cycle failed: {str(e)[:100]}")
    finally:
        del universe_raw
        del universe_data
        gc.collect()

def run_schedule_wrapper():
    asyncio.create_task(run_live_cycle())

async def heartbeat_task():
    bal = broker.get_account_balance()
    open_pos = len(broker.get_open_positions())
    await async_send_telegram_message(f"🟢 <b>SYSTEM ACTIVE</b>\nBalance: ${bal:.2f}\nOpen Positions: {open_pos}")

def run_heartbeat_wrapper():
    asyncio.create_task(heartbeat_task())

async def train_ml_task():
    """Async task to retrain the ML model on weekends."""
    logger.info("Starting scheduled ML Retraining...")
    try:
        universe_raw = await DataLoader.get_all_universe_data()

        # Extract only the hourly data DataFrames for training
        training_data = {}
        for ticker, (daily, hourly) in universe_raw.items():
            try:
                # Add features before passing to ML
                h_feat = add_features(hourly, "1h")
                training_data[ticker] = h_feat
            except Exception as e:
                logger.error(f"Feature error for {ticker} during ML prep: {e}")

        await MLValidator.async_train_model(training_data)
        await async_send_telegram_message("🤖 <b>ML Model Retrained Successfully</b>\nRandomForest ready for next week.")
    except Exception as e:
        logger.error(f"Error in scheduled ML Retraining: {e}")

def run_ml_train_wrapper():
    asyncio.create_task(train_ml_task())

async def generate_tear_sheet_task():
    """Async task to generate weekly reports."""
    try:
        await TearSheetReporter.generate_report()
    except Exception as e:
        logger.error(f"Error generating Tear Sheet: {e}")

def run_tear_sheet_wrapper():
    asyncio.create_task(generate_tear_sheet_task())


# --- TELEGRAM BOT HANDLERS ---
def verify_admin(update: Update) -> bool:
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        logger.critical(f"UNAUTHORIZED ACCESS ATTEMPT from ID: {update.effective_chat.id}")
        return False
    return True

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_admin(update): return
    bal = broker.get_account_balance()
    pos = broker.get_open_positions()
    msg = f"📊 <b>STATUS</b>\nBalance: ${bal:.2f}\nOpen Trades: {len(pos)}\nPaused: {is_paused}"
    await update.message.reply_html(msg)

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if not verify_admin(update): return
    is_paused = True
    await update.message.reply_html("⏸️ <b>PAUSED</b>\nNew entries halted.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global is_paused
    if not verify_admin(update): return
    is_paused = False
    await update.message.reply_html("▶️ <b>RESUMED</b>\nAutonomous scanning active.")

async def cmd_panic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_admin(update): return
    global broker
    pos = broker.get_open_positions()
    if not pos:
        await update.message.reply_html("No open trades to close.")
        return

    await update.message.reply_html("🚨 <b>PANIC BUTTON ACTIVATED</b>\nClosing all positions at market...")
    asyncio.create_task(async_panic_close(pos))

async def async_panic_close(positions):
    universe = await DataLoader.get_all_universe_data()
    for p in positions:
        ticker = p['ticker']
        if ticker in universe and universe[ticker][1] is not None:
            latest = universe[ticker][1].iloc[-1]['Close']
            atr = universe[ticker][1].iloc[-1]['ATR_14']
            exit_price = ExecutionSimulator.execute_trade_price(ticker, latest, -1 if p['direction'] == 'Long' else 1, pd.Series([atr]))
            broker.close_position(p['trade_id'], exit_price, reason="PANIC_BUTTON")
    await async_send_telegram_message("✅ <b>PANIC CLOSE COMPLETE</b>\nAll positions closed.")

async def cmd_force_scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_admin(update): return
    await update.message.reply_html("🔍 <b>FORCE SCAN INITIATED</b>\nScanning universe...")
    asyncio.create_task(run_live_cycle())

async def main():
    """Main Application Loop"""
    logger.info("Initializing ED Capital Quant Engine...")

    bal = broker.get_account_balance()
    logger.info(f"State Recovered. Current Balance: ${bal:.2f}")

    # Telegram Boot
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("durum", cmd_status))
    application.add_handler(CommandHandler("durdur", cmd_pause))
    application.add_handler(CommandHandler("devam", cmd_resume))
    application.add_handler(CommandHandler("kapat_hepsi", cmd_panic))
    application.add_handler(CommandHandler("tara", cmd_force_scan))

    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    logger.info("Telegram interface listening for admin commands.")
    await async_send_telegram_message(f"🚀 <b>ED Capital Quant Engine Started</b>\nBalance: ${bal:.2f}")

    # Initial ML Training trigger (If model does not exist)
    if not __import__('os').path.exists(MLValidator.MODEL_PATH):
        logger.info("Initial Boot: Triggering ML Model Training...")
        asyncio.create_task(train_ml_task())

    # Schedule Main Tasks
    schedule.every().hour.at(":01").do(run_schedule_wrapper)
    schedule.every().day.at("08:00").do(run_heartbeat_wrapper)

    # Phase 18: Auto-Retrain ML Model every Sunday at 23:00
    schedule.every().sunday.at("23:00").do(run_ml_train_wrapper)

    # Phase 13 & 22: Generate Tear Sheet (with Monte Carlo) every Friday at 23:30 (Market Close)
    schedule.every().friday.at("23:30").do(run_tear_sheet_wrapper)

    logger.info("Scheduler started. Entering main loop...")

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Engine shutting down (KeyboardInterrupt).")
    except Exception as e:
        logger.critical(f"Fatal Engine Crash: {e}")
