import os
import sys
import asyncio
import time
import schedule
import pandas as pd
import gc
from datetime import datetime, timedelta
from dotenv import load_dotenv

from logger import log
from paper_db import init_db
from data_loader import fetch_mtf_data, align_mtf_data, UNIVERSE
from features import add_features
from strategy import check_signals
from macro_filter import get_market_regime, is_black_swan_vix, is_flash_crash
from sentiment_filter import update_sentiment_cache
from portfolio_manager import calculate_correlation_matrix, check_global_limits
from execution_model import calculate_dynamic_execution_price
from ml_validator import train_model
from reporter import generate_tear_sheet
import notifier
from brokers.paper_broker import PaperBroker

# Load Environment Config
load_dotenv()
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", 10000.0))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", 4))
GLOBAL_EXPOSURE_LIMIT = float(os.getenv("GLOBAL_EXPOSURE_LIMIT", 0.06))

# Dependency Injection: PaperBroker (Replaceable with LiveBroker later)
broker = PaperBroker(initial_capital=INITIAL_CAPITAL)

async def manage_open_positions():
    """
    Phase 12: Manages existing trades (Trailing Stop & Breakeven logic).
    Must NOT be skipped even during Black Swans.
    """
    open_trades = broker.get_open_positions()
    if not open_trades:
        return

    for trade in open_trades:
        try:
            ticker = trade['ticker']
            trade_id = trade['trade_id']
            direction = trade['direction']
            entry_price = trade['entry_price']
            sl_price = trade['sl_price']
            tp_price = trade['tp_price']
            highest_seen = trade['highest_price']
            lowest_seen = trade['lowest_price']

            # Fetch current latest price (Fast fetch for open positions)
            htf, ltf = await fetch_mtf_data(ticker, "5d", "5d")
            if ltf is None or ltf.empty:
                continue

            current_price = ltf['close'].iloc[-1]
            atr = add_features(ltf)['ATR_14'].iloc[-1]
            if pd.isna(atr): atr = current_price * 0.01

            # Update highest/lowest for Trailing logic
            if current_price > highest_seen:
                highest_seen = current_price
                broker.update_high_low(trade_id, highest_seen, lowest_seen)
            if current_price < lowest_seen:
                lowest_seen = current_price
                broker.update_high_low(trade_id, highest_seen, lowest_seen)

            # Execution Simulator for Exit
            exit_price, _, slippage = calculate_dynamic_execution_price(ticker, "Close", current_price, add_features(ltf))

            # -----------------------------------------------------------------
            # 1. Trailing Stop & Breakeven Update (Monotonic)
            # -----------------------------------------------------------------
            if direction == "Long":
                # Breakeven: If profit > 1.0 ATR
                if current_price >= entry_price + (1.0 * atr) and sl_price < entry_price:
                    broker.modify_trailing_stop(trade_id, entry_price)
                    await notifier.send_telegram_async(f"🔒 Risk Sıfırlandı: [{ticker}] Long SL seviyesi giriş fiyatına çekildi.")

                # Trailing Stop: Update to Highest - 1.5 ATR
                new_sl = highest_seen - (1.5 * atr)
                if new_sl > sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl)

                # TP/SL Hit Check
                if current_price <= sl_price:
                    res = broker.close_position(trade_id, exit_price, reason="SL")
                    await notifier.send_telegram_async(f"❌ Kapanış (SL): {ticker} Long | PnL: ${res.get('pnl', 0):.2f}")
                elif current_price >= tp_price:
                    res = broker.close_position(trade_id, exit_price, reason="TP")
                    await notifier.send_telegram_async(f"✅ Kapanış (TP): {ticker} Long | PnL: ${res.get('pnl', 0):.2f}")

            elif direction == "Short":
                # Breakeven: If profit > 1.0 ATR (lower price is profit)
                if current_price <= entry_price - (1.0 * atr) and sl_price > entry_price:
                    broker.modify_trailing_stop(trade_id, entry_price)
                    await notifier.send_telegram_async(f"🔒 Risk Sıfırlandı: [{ticker}] Short SL seviyesi giriş fiyatına çekildi.")

                # Trailing Stop: Update to Lowest + 1.5 ATR
                new_sl = lowest_seen + (1.5 * atr)
                if new_sl < sl_price: # Strictly monotonic
                    broker.modify_trailing_stop(trade_id, new_sl)

                # TP/SL Hit Check
                if current_price >= sl_price:
                    res = broker.close_position(trade_id, exit_price, reason="SL")
                    await notifier.send_telegram_async(f"❌ Kapanış (SL): {ticker} Short | PnL: ${res.get('pnl', 0):.2f}")
                elif current_price <= tp_price:
                    res = broker.close_position(trade_id, exit_price, reason="TP")
                    await notifier.send_telegram_async(f"✅ Kapanış (TP): {ticker} Short | PnL: ${res.get('pnl', 0):.2f}")

        except Exception as e:
            log.error(f"Error managing position {trade_id} ({ticker}): {e}")

async def run_live_cycle():
    """
    Phase 23: The main live trading pipeline.
    Executes sequentially: Market Checks -> Manage Opens -> Find New Signals -> Execute.
    """
    try:
        log.info("--- Starting Live Cycle ---")
        current_capital = broker.get_account_balance()

        # Step 1: Manage Existing Positions (Never skip this)
        await manage_open_positions()

        # Step 2: System Pause Check (Admin Command)
        if notifier.SYSTEM_PAUSED:
            log.info("System is Paused via Telegram. Skipping new signal generation.")
            return

        # Step 3: Macro & Black Swan Vetoes (Phase 19)
        if is_black_swan_vix(threshold=35.0):
            log.critical("VIX Circuit Breaker Active. Skipping new long signals.")
            return # Optionally, you could allow Short signals, but VIX > 35 means extreme cash demand. Safer to halt.

        regime = get_market_regime()
        log.info(f"Market Regime: {regime}")

        # Step 4: Update Sentiment & Correlation Caches
        update_sentiment_cache()
        corr_matrix = calculate_correlation_matrix()

        # Step 5: Check Global Limits
        open_trades = broker.get_open_positions()
        if check_global_limits(open_trades, MAX_POSITIONS, GLOBAL_EXPOSURE_LIMIT, current_capital):
            return

        # Step 6: Scan Universe for New Signals
        for name, ticker in UNIVERSE.items():
            try:
                # MTF Data Fetch
                htf_df, ltf_df = await fetch_mtf_data(ticker)
                if htf_df is None or ltf_df is None: continue

                # Z-Score Flash Crash Check
                if is_flash_crash(ltf_df, ticker):
                    continue

                # Feature Engineering
                htf_feat = add_features(htf_df, is_htf=True)
                ltf_feat = add_features(ltf_df, is_htf=False)

                # Align Data strictly (Lookahead Bias Prevention)
                aligned_df = align_mtf_data(htf_feat, ltf_feat)

                # Strategy Engine (MTF Confluence + ML Veto + NLP Veto + Kelly)
                signal_data = check_signals(ticker, aligned_df, current_capital, open_trades, corr_matrix)

                if signal_data:
                    # Realistic Execution Modeling (Spread + Slippage)
                    exec_price, spread, slippage = calculate_dynamic_execution_price(
                        ticker, signal_data['direction'], signal_data['entry_price'], ltf_feat
                    )

                    # Execute via Broker Abstraction Layer
                    res = broker.place_market_order(
                        ticker=ticker,
                        direction=signal_data['direction'],
                        size=signal_data['position_size'],
                        entry_price=exec_price,
                        sl_price=signal_data['sl_price'],
                        tp_price=signal_data['tp_price']
                    )

                    if res['status'] == "Success":
                        msg = f"🚀 <b>YENİ GİRİŞ: {ticker}</b>\n"
                        msg += f"Yön: {signal_data['direction']}\n"
                        msg += f"İşlem Fiyatı: {exec_price:.4f} (Kayma+Makas: {(spread+slippage):.4f})\n"
                        msg += f"Stop Loss: {signal_data['sl_price']:.4f}\n"
                        msg += f"Take Profit: {signal_data['tp_price']:.4f}\n"
                        msg += f"Lot/Sözleşme: {signal_data['position_size']:.2f}\n"
                        msg += f"Kasa Riski: %{(signal_data['risk_pct']*100):.2f}\n"
                        await notifier.send_telegram_async(msg)

            except Exception as e:
                log.error(f"Error processing {ticker} in live cycle: {e}")

    except Exception as e:
        log.critical(f"Critical error in main cycle: {e}")
    finally:
        # Garbage Collection (Memory Management Phase 23)
        gc.collect()

async def send_daily_heartbeat():
    """Phase 8: Daily status report."""
    capital = broker.get_account_balance()
    open_trades = len(broker.get_open_positions())
    msg = f"🟢 <b>Günlük Sistem Raporu</b>\nKasa: ${capital:.2f}\nAçık Pozisyon: {open_trades}\nSistem Aktif."
    await notifier.send_telegram_async(msg)

def run_weekly_tasks():
    """Phase 18 & 13: Auto-retrain ML model and generate Tear Sheet on weekends."""
    log.info("Running Weekly Maintenance Tasks...")
    train_model() # Retrain Random Forest

    # Generate and send PDF/HTML Report
    report_path = generate_tear_sheet(INITIAL_CAPITAL)
    if report_path:
        # We can't easily send files async via requests without multipart/form-data setup
        # For simplicity, we just send a success message. In production, use standard bot API.
        log.info(f"Weekly Tear Sheet Ready: {report_path}")

async def wait_for_next_hour():
    """Synchronizes execution strictly at the start of the hour (minute 0, second 1)."""
    now = datetime.now()
    # Calculate time until next hour + 1 second buffer
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=1, microsecond=0)
    sleep_seconds = (next_hour - now).total_seconds()
    log.info(f"Sleeping for {sleep_seconds:.1f} seconds until next hourly candle close ({next_hour.strftime('%H:%M:%S')}).")
    await asyncio.sleep(sleep_seconds)

async def main():
    """
    Main Async Event Loop initializing the Telegram bot and Trading Engine.
    """
    log.info("ED Capital Quant Engine Starting...")
    init_db()

    # Initialize Telegram Bot
    app = await notifier.setup_telegram_bot()
    if app:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await notifier.send_telegram_async("🚀 ED Capital Quant Engine Başlatıldı. Sistem Devrede.")

    # Schedule Tasks (Synchronous wrapper inside async loop)
    schedule.every().day.at("08:00").do(lambda: asyncio.create_task(send_daily_heartbeat()))
    schedule.every().friday.at("23:00").do(run_weekly_tasks)

    # Initial ML Training if missing
    import os
    if not os.path.exists('models/rf_model.joblib'):
        log.info("No ML model found. Triggering initial training...")
        train_model()

    try:
        while True:
            # 1. Run any pending scheduled tasks (Heartbeat, Tear Sheet)
            schedule.run_pending()

            # 2. Wait exactly for the next hourly candle to close
            await wait_for_next_hour()

            # 3. Execute Trading Cycle
            await run_live_cycle()

    except asyncio.CancelledError:
        log.info("Main loop cancelled. Shutting down...")
    except Exception as e:
        log.critical(f"Fatal error in main loop: {e}")
    finally:
        if app:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot manually stopped by user.")
