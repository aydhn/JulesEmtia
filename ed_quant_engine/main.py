import time
import schedule
import asyncio
import gc
import sys
from datetime import datetime, timezone
import pandas as pd

from config import TICKERS, MAX_OPEN_POSITIONS, MAX_TOTAL_EXPOSURE_PCT
from logger import get_logger
from paper_db import init_db, get_open_positions, close_trade, get_closed_trades
from broker import PaperBroker
from data_loader import fetch_mtf_data, merge_mtf
from features import add_features
from signals import generate_signals
from macro_filter import check_vix_circuit_breaker, check_zscore_flash_crash, get_macro_regime
from sentiment_filter import analyze_sentiment
from portfolio_manager import calculate_correlation_matrix, check_correlation_veto, check_global_limits
from execution_model import calculate_dynamic_slippage, apply_execution_costs
from risk_manager import calculate_kelly_fraction, trailing_stop_logic
from ml_validator import predict_proba_veto, train_model
from notifier import TelegramNotifier
from reporter import generate_tear_sheet
from analysis import run_monte_carlo

log = get_logger()
broker = PaperBroker()
notifier = TelegramNotifier()

# Global State
IS_PAUSED = False
corr_matrix = pd.DataFrame()

def recover_state():
    """Reads SQLite to rebuild open positions on reboot (Phase 8)."""
    open_trades = get_open_positions()
    if open_trades:
        notifier.send_message(f"🔄 State Recovery: Resuming tracking of {len(open_trades)} open positions.")
        log.info(f"Recovered {len(open_trades)} open trades.")
    else:
        log.info("No open trades to recover.")

def update_correlation_matrix():
    """Periodic task to refresh correlation matrix (Phase 11)."""
    global corr_matrix
    all_tickers = []
    for cats in TICKERS.values(): all_tickers.extend(cats)
    corr_matrix = calculate_correlation_matrix(all_tickers)
    log.info("Correlation matrix updated.")

def manage_open_positions(latest_prices: dict, atrs: dict):
    """Trailing Stop strictly monotonic & TP/SL checks (Phases 5, 12, 19)."""
    open_trades = broker.get_open_trades()
    black_swan = check_vix_circuit_breaker()

    for t in open_trades:
        trade_id, ticker, direction, en_time, en_price, sl_price, tp_price, qty, status, ex_time, ex_price, pnl, cost = t

        if ticker not in latest_prices: continue

        current_price = latest_prices[ticker]
        atr = atrs.get(ticker, 0.0)

        # 1. Black Swan Aggressive Exit
        if black_swan:
            log.critical(f"BLACK SWAN: Force closing {ticker}")
            exit_p = apply_execution_costs(direction, current_price, cost)
            calc_pnl = (exit_p - en_price) * qty if direction == "Long" else (en_price - exit_p) * qty
            broker.close_position(trade_id, exit_p, str(datetime.now(timezone.utc)), calc_pnl)
            notifier.send_message(f"🚨 BLACK SWAN EXIT: {direction} {ticker} @ {exit_p:.2f} | PnL: {calc_pnl:.2f}")
            continue

        # 2. Check TP/SL
        hit_tp = (direction == "Long" and current_price >= tp_price) or (direction == "Short" and current_price <= tp_price)
        hit_sl = (direction == "Long" and current_price <= sl_price) or (direction == "Short" and current_price >= sl_price)

        if hit_tp or hit_sl:
            exit_p = apply_execution_costs(direction, current_price, cost)
            calc_pnl = (exit_p - en_price) * qty if direction == "Long" else (en_price - exit_p) * qty
            broker.close_position(trade_id, exit_p, str(datetime.now(timezone.utc)), calc_pnl)
            res = "TP HIT" if hit_tp else "SL HIT"
            notifier.send_message(f"🏁 {res}: Closed {direction} {ticker} @ {exit_p:.2f} | PnL: {calc_pnl:.2f}")
            continue

        # 3. Trailing Stop
        new_sl = trailing_stop_logic(direction, current_price, en_price, sl_price, atr)
        if new_sl != sl_price:
            broker.modify_trailing_stop(trade_id, new_sl)
            log.info(f"Trailing SL moved for {ticker} to {new_sl:.4f}")

def run_live_cycle():
    """Main Orchestrator Pipeline (Phase 23)."""
    global IS_PAUSED, corr_matrix
    if IS_PAUSED:
        log.info("System is PAUSED. Skipping scan.")
        return

    log.info("--- Starting MTF Live Cycle ---")

    # 0. VIX Circuit Breaker (Phase 19)
    if check_vix_circuit_breaker():
        log.warning("Scan aborted due to VIX Circuit Breaker.")
        return

    open_trades = broker.get_open_trades()

    # 1. Check Global Limits (Phase 11)
    if check_global_limits(open_trades, broker.get_account_balance()):
        return

    latest_prices = {}
    atrs = {}

    # Process each ticker
    for category, t_list in TICKERS.items():
        for ticker in t_list:
            try:
                # 2. Fetch MTF (Phase 16)
                htf_df, ltf_df = fetch_mtf_data(ticker)
                htf_feat = add_features(htf_df, is_htf=True)
                ltf_feat = add_features(ltf_df, is_htf=False)

                merged = merge_mtf(htf_feat, ltf_feat)
                if merged.empty: continue

                latest = merged.iloc[-1]
                latest_prices[ticker] = latest['Close']
                atrs[ticker] = latest['ATR_14']

                # Z-Score Anomaly (Phase 19)
                if check_zscore_flash_crash(merged): continue

                # 3. Strategy MTF Confluence (Phase 4, 16)
                signal = generate_signals(merged)
                if not signal: continue

                direction = signal['direction']
                price = signal['price']
                atr = signal['atr']

                log.info(f"Signal Detected: {direction} {ticker}")

                # 4. Correlation Veto (Phase 11)
                if check_correlation_veto(ticker, direction, open_trades, corr_matrix):
                    continue

                # 5. ML Validator Veto (Phase 18)
                features_dict = latest.to_dict()
                if predict_proba_veto(features_dict):
                    continue

                # 6. Sentiment Veto (Phase 20)
                sentiment_score = analyze_sentiment(ticker, keywords=[ticker.split("=")[0], "inflation", "fed"])
                if (direction == "Long" and sentiment_score < -0.5) or (direction == "Short" and sentiment_score > 0.5):
                    log.warning(f"SENTIMENT VETO: Fundamental mismatch for {ticker} (Score: {sentiment_score:.2f})")
                    continue

                # 7. Execution & Sizing (Phase 15, 21)
                slip_cost = calculate_dynamic_slippage(ticker, atr, price)
                exec_price = apply_execution_costs(direction, price, slip_cost)

                closed_df = pd.DataFrame(get_closed_trades(), columns=['id', 'ticker', 'dir', 'en_time', 'en_price', 'sl', 'tp', 'qty', 'status', 'ex_time', 'ex_price', 'pnl', 'cost'])
                risk_pct = calculate_kelly_fraction(closed_df)

                risk_usd = broker.get_account_balance() * risk_pct
                sl_dist = 1.5 * atr
                qty = risk_usd / sl_dist if sl_dist > 0 else 0

                if qty <= 0: continue

                tp = exec_price + (3.0 * atr) if direction == "Long" else exec_price - (3.0 * atr)
                sl = exec_price - sl_dist if direction == "Long" else exec_price + sl_dist

                # 8. Fire!
                receipt = broker.place_market_order(ticker, direction, qty, exec_price, sl, tp, slip_cost, str(datetime.now(timezone.utc)))

                msg = f"🟢 NEW TRADE: {direction} <b>{ticker}</b>\n"
                msg += f"Price: {exec_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\n"
                msg += f"Size: {qty:.2f} units (Risk: {risk_pct:.2%})\n"
                msg += f"Kelly: Active | ML: Approved"
                notifier.send_message(msg)

            except Exception as e:
                log.error(f"Error processing {ticker}: {e}")

    # Update trailing stops for all open positions based on latest fetched prices
    manage_open_positions(latest_prices, atrs)

    # Memory Management (Phase 23)
    del latest_prices
    del atrs
    gc.collect()

def generate_weekly_report():
    """Generates Tearsheet and Monte Carlo (Phase 13, 22)."""
    closed = get_closed_trades()
    if closed:
        df = pd.DataFrame(closed, columns=['id', 'ticker', 'dir', 'en_time', 'en_price', 'sl', 'tp', 'qty', 'status', 'ex_time', 'ex_price', 'pnl', 'cost'])
        mc_results = run_monte_carlo(df['pnl'].tolist(), n_simulations=10000, initial_capital=broker.get_account_balance())
        path = generate_tear_sheet(mc_results)
        if path:
            notifier.send_report(path)

if __name__ == "__main__":
    init_db()
    recover_state()
    update_correlation_matrix()

    notifier.send_message("🚀 ED Capital Quant Engine Live Paper Trade Mode Initialized.\nVIX Circuit Breakers: Armed.\nML Validator: Active.")

    # Strict candle-close sync (top of the hour)
    schedule.every().hour.at(":00").do(run_live_cycle)

    # Weekly matrix update & reporting
    schedule.every().monday.at("00:00").do(update_correlation_matrix)
    schedule.every().friday.at("22:00").do(generate_weekly_report)

    # Run once at startup for testing
    run_live_cycle()

    log.info("Entering main loop...")
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            log.info("Engine stopped by user.")
            sys.exit(0)
        except Exception as e:
            log.error(f"Critical Main Loop Error: {e}")
            time.sleep(60)
