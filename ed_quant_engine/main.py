import asyncio
import schedule
import time
import os
import gc
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

from src.logger import get_logger
from src.notifier import send_telegram_message_async, send_telegram_document_async, notify_critical_error, start_telegram_listener, global_state
from src.broker import PaperBroker
from src.data_loader import fetch_universe_async, align_mtf_data, UNIVERSE
from src.features import add_features, calculate_z_score
from src.macro_filter import fetch_macro_regime, apply_macro_veto
from src.sentiment_filter import check_sentiment_veto
from src.portfolio_manager import check_global_exposure, check_correlation_veto, calculate_correlation_matrix, get_dynamic_position_size
from src.strategy import generate_signals
from src.execution_model import apply_execution_costs
from src.ml_validator import check_ml_veto, train_model
from src.reporter import generate_tear_sheet

load_dotenv()
logger = get_logger("main")

broker = PaperBroker(initial_balance=10000.0)

async def check_open_positions_task(vix_spike_active: bool = False):
    """Checks TP/SL and Trailing Stop logic. Aggressive defense if VIX Spike is active."""
    try:
        open_positions = broker.get_open_positions()
        if not open_positions: return

        import yfinance as yf
        tickers = list(set([p['ticker'] for p in open_positions]))
        df_prices = yf.download(tickers, period="1d", interval="1m", progress=False)['Close']

        if isinstance(df_prices, pd.Series):
            current_prices = {tickers[0]: df_prices.iloc[-1]}
        else:
            current_prices = {t: df_prices[t].iloc[-1] for t in tickers}

        for p in open_positions:
            ticker = p['ticker']
            if ticker not in current_prices: continue

            curr_price = current_prices[ticker]
            entry_price = p['entry_price']
            sl_price = p['sl_price']
            tp_price = p['tp_price']
            direction = p['direction']
            lot_size = p['position_size']

            # Realistic costs
            exit_price = apply_execution_costs(ticker, "Close", curr_price, 0.0, 0.0)

            # 1. Stop Loss Hit
            if (direction == "Long" and exit_price <= sl_price) or (direction == "Short" and exit_price >= sl_price):
                pnl = (exit_price - entry_price) * lot_size if direction == "Long" else (entry_price - exit_price) * lot_size
                broker.close_position(p['trade_id'], exit_price, pnl, "Stop Loss Hit")
                await send_telegram_message_async(f"🛑 <b>Stop Loss Hit</b>\n{ticker} {direction}\nEntry: {entry_price:.4f}\nExit: {exit_price:.4f}\nPNL: ${pnl:.2f}")
                continue

            # 2. Take Profit Hit
            if (direction == "Long" and exit_price >= tp_price) or (direction == "Short" and exit_price <= tp_price):
                pnl = (exit_price - entry_price) * lot_size if direction == "Long" else (entry_price - exit_price) * lot_size
                broker.close_position(p['trade_id'], exit_price, pnl, "Take Profit Hit")
                await send_telegram_message_async(f"✅ <b>Take Profit Hit</b>\n{ticker} {direction}\nEntry: {entry_price:.4f}\nExit: {exit_price:.4f}\nPNL: ${pnl:.2f}")
                continue

            # 3. Breakeven / Trailing Stop Logic & VIX Defense
            dist_to_tp = abs(tp_price - entry_price)
            curr_dist = abs(curr_price - entry_price)

            # If Black Swan (VIX Spike) is active, move SL aggressively to breakeven if in profit, or panic close.
            if vix_spike_active:
                if (direction == "Long" and curr_price > entry_price) or (direction == "Short" and curr_price < entry_price):
                    if (direction == "Long" and sl_price < entry_price) or (direction == "Short" and sl_price > entry_price):
                        broker.modify_stop_loss(p['trade_id'], entry_price)
                        await send_telegram_message_async(f"🚨 <b>VIX Defense</b>\n{ticker} SL aggressively moved to breakeven ({entry_price:.4f})")

            # Normal Trailing logic
            elif curr_dist > (dist_to_tp * 0.5):
                if (direction == "Long" and sl_price < entry_price) or (direction == "Short" and sl_price > entry_price):
                    broker.modify_stop_loss(p['trade_id'], entry_price)
                    await send_telegram_message_async(f"🔒 <b>Risk Free</b>\n{ticker} SL moved to entry ({entry_price:.4f})")

    except Exception as e:
        logger.error(f"Error checking open positions: {e}")

async def run_live_cycle():
    logger.info("Starting Live Scan Cycle...")
    try:
        # 1. Macro Regime Check (VIX Spike)
        macro_state = fetch_macro_regime()
        vix_spike = macro_state["VIX_Spike"]

        if vix_spike:
            logger.critical("VIX Spike detected! Defensive mode engaged. New operations halted.")
            await send_telegram_message_async("🚨 <b>VIX CIRCUIT BREAKER ENGAGED!</b>\nNew trades halted. Open positions are under aggressive defense.")

        # 2. Check Open Positions & Manage Risk ALWAYS runs, even if VIX spiked or paused
        await check_open_positions_task(vix_spike_active=vix_spike)

        # If system is paused by admin OR VIX is spiking, skip new trade generation
        if global_state.get("is_paused", False) or vix_spike:
            logger.info("System is Paused or VIX is Spiking. Skipping new scan.")
            return

        # 3. Check Capacity
        if check_global_exposure(0.06): return

        # 4. Fetch Data (MTF)
        ltf_data = await fetch_universe_async("1h", "1mo")
        htf_data = await fetch_universe_async("1d", "6mo")

        if not ltf_data or not htf_data:
            logger.error("Data fetch returned empty. Aborting cycle.")
            return

        corr_matrix = calculate_correlation_matrix(htf_data)

        # 5. Signal Generation Loop
        for ticker in UNIVERSE.keys():
            if ticker not in ltf_data or ticker not in htf_data: continue

            df_ltf = add_features(ltf_data[ticker])
            df_htf = add_features(htf_data[ticker])

            if df_ltf.empty or df_htf.empty: continue

            # Micro Flash Crash / Z-Score Anomaly Detection
            df_ltf['Z_Score'] = calculate_z_score(df_ltf['Close'], window=50)
            z_score_current = df_ltf['Z_Score'].iloc[-1]

            if abs(z_score_current) > 4.0:
                logger.warning(f"Z-Score Anomaly VETO: {ticker} has Z-Score {z_score_current:.2f}. Halting operations for this asset.")
                continue # Skip this asset for this cycle

            # Align Timeframes
            df_aligned = align_mtf_data(df_ltf, df_htf)

            # Strategy Eval
            signal, sl_dist, tp_dist = generate_signals(df_aligned)
            if not signal: continue

            current_row = df_aligned.iloc[-1].to_dict()
            market_price = current_row['Close']

            # --- VETO CHECKS ---
            if apply_macro_veto(signal, macro_state["Regime"], ticker): continue
            if check_correlation_veto(ticker, signal, corr_matrix): continue
            if check_ml_veto(current_row): continue
            if check_sentiment_veto(ticker, signal): continue

            # --- EXECUTION ---
            current_atr = current_row['ATR_14']
            avg_atr = df_aligned['ATR_14'].mean()

            entry_price = apply_execution_costs(ticker, signal, market_price, current_atr, avg_atr)

            sl_price = entry_price - sl_dist if signal == "Long" else entry_price + sl_dist
            tp_price = entry_price + tp_dist if signal == "Long" else entry_price - tp_dist

            lot_size = get_dynamic_position_size(ticker, broker.get_account_balance(), entry_price, sl_price)
            if lot_size <= 0: continue

            # Open Trade
            receipt = broker.place_market_order(ticker, signal, entry_price, sl_price, tp_price, lot_size, "MTF-Confirmed")

            msg = f"🚀 <b>NEW {signal} SIGNAL EXECUTED</b>\n\n<b>Asset:</b> {ticker}\n<b>Entry:</b> {entry_price:.4f}\n<b>SL:</b> {sl_price:.4f}\n<b>TP:</b> {tp_price:.4f}\n<b>Size:</b> {lot_size:.4f} Lots"
            await send_telegram_message_async(msg)

    except Exception as e:
        notify_critical_error(e, "run_live_cycle")
    finally:
        gc.collect()
        logger.info("Cycle completed. Memory cleaned.")

def heartbeat():
    bal = broker.get_account_balance()
    open_pos = len(broker.get_open_positions())
    msg = f"🟢 <b>ED Quant Engine Heartbeat</b>\n\n<b>Status:</b> Active & Scanning\n<b>Balance:</b> ${bal:,.2f}\n<b>Open Positions:</b> {open_pos}\n<b>VIX/Regime OK.</b>"
    asyncio.create_task(send_telegram_message_async(msg))

def weekly_report():
    report_path = generate_tear_sheet(10000.0)
    if report_path:
        asyncio.create_task(send_telegram_document_async(report_path, "ED Capital Haftalık Performans Raporu"))

async def ml_retraining_task():
    """Background task to fetch historical data and retrain the ML model."""
    logger.info("Initiating Weekend ML Model Retraining...")
    await send_telegram_message_async("🧠 <b>ML Model Retraining:</b> Fetching historical data to update Random Forest logic...")
    try:
        # Fetch long-term daily data for Gold as a primary proxy for training features
        # In a real setup, we would concatenate features across the whole universe.
        import yfinance as yf
        df = yf.download("GC=F", period="5y", interval="1d", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = add_features(df)
        success = train_model(df)

        if success:
            await send_telegram_message_async("✅ <b>ML Model Updated Successfully.</b> Random Forest is ready for the new week.")
        else:
            await send_telegram_message_async("⚠️ <b>ML Model Update Failed.</b> Will continue using the existing/old model.")
    except Exception as e:
        logger.error(f"ML Retraining failed: {e}")

def trigger_ml_retraining():
    asyncio.create_task(ml_retraining_task())

async def schedule_loop():
    schedule.every().hour.at(":00").do(lambda: asyncio.create_task(run_live_cycle()))
    schedule.every().day.at("08:00").do(heartbeat)
    schedule.every().friday.at("22:00").do(weekly_report)

    # Weekly ML Retraining (e.g., Saturday night when markets are closed)
    schedule.every().saturday.at("23:00").do(trigger_ml_retraining)

    logger.info("Scheduler started. Waiting for triggers...")

    await start_telegram_listener()
    await send_telegram_message_async("🚀 <b>ED Capital Quant Engine Started</b>\nAll modules loaded. Wait for MTF sync cycle.")

    # Run initial ML training if the model file doesn't exist yet
    if not os.path.exists("models/rf_validator.joblib"):
        trigger_ml_retraining()

    while True:
        schedule.run_pending()

        if global_state.get("force_scan", False):
            logger.info("Force scan triggered via Telegram.")
            global_state["force_scan"] = False
            asyncio.create_task(run_live_cycle())

        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(schedule_loop())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"Fatal error in main loop: {e}")
