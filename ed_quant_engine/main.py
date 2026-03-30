import schedule
import time
import pandas as pd
import gc
from core.config import FLAT_TICKERS, VIX_BLACK_SWAN_THRESHOLD, Z_SCORE_ANOMALY
from core.logger import get_logger
from core.telegram_notifier import send_message
from data.loader import fetch_data
from data.features import add_features
from data.macro import get_vix, get_dxy_trend
from data.nlp import get_news_sentiment
from strategy.logic import generate_signals
from strategy.ml_validator import validate_signal, train_model
from strategy.execution import execute_cost_model
from trading.portfolio import calculate_correlation, check_correlation_veto, calculate_kelly_size
from trading.trade_manager import check_open_positions
from db.paper_broker import PaperBroker

log = get_logger()
broker = PaperBroker()

# State management
app_state = {'paused': False}

def run_live_cycle():
    if app_state['paused']:
        log.info("System is Paused. Skipping scan.")
        return

    log.info("Starting Live Cycle Scan...")

    # 1. Macro & Black Swan checks
    vix = get_vix()
    dxy_trend = get_dxy_trend()
    log.info(f"VIX: {vix:.2f} | DXY Trend: {dxy_trend}")

    black_swan_active = False
    if vix > VIX_BLACK_SWAN_THRESHOLD:
        log.warning("VIX Black Swan Active! Halting new long positions.")
        send_message(f"🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi ({vix:.2f})! Sistem Savunma Moduna Geçti.")
        black_swan_active = True

    # 2. Fetch Data & Features
    dfs_htf = {}
    dfs_ltf = {}
    current_prices = {}
    current_atrs = {}

    for ticker in FLAT_TICKERS:
        df_1d = fetch_data(ticker, '1d', '2y')
        df_1h = fetch_data(ticker, '1h', '60d')

        if df_1d.empty or df_1h.empty:
            continue

        df_1d = add_features(df_1d)
        df_1h = add_features(df_1h)

        dfs_htf[ticker] = df_1d
        dfs_ltf[ticker] = df_1h

        current_prices[ticker] = df_1h['Close'].iloc[-1]
        current_atrs[ticker] = df_1h['ATR_14'].iloc[-1]

    # 3. Manage Open Positions
    check_open_positions(broker, current_prices, current_atrs)

    if black_swan_active:
        return # Skip finding new signals

    # 4. Correlation Matrix
    corr_matrix = calculate_correlation(dfs_1h) if 'dfs_1h' in locals() else calculate_correlation(dfs_ltf)

    # 5. Signal Generation & Validation
    for ticker, df in dfs_ltf.items():
        signals_df = generate_signals(df)
        latest_signal = signals_df['Signal'].iloc[-1]

        if latest_signal == 0:
            continue

        direction = 'Long' if latest_signal == 1 else 'Short'

        # MTF Veto (Daily trend must align)
        if ticker in dfs_htf:
            daily_ema = dfs_htf[ticker]['EMA_50'].iloc[-1]
            daily_close = dfs_htf[ticker]['Close'].iloc[-1]
            if direction == 'Long' and daily_close < daily_ema:
                log.info(f"MTF Veto for {ticker}: Daily trend is down.")
                continue
            elif direction == 'Short' and daily_close > daily_ema:
                log.info(f"MTF Veto for {ticker}: Daily trend is up.")
                continue

        # ML Validator
        prob = validate_signal(signals_df)
        if prob < 0.60:
            log.info(f"ML Veto for {ticker}: Low Probability ({prob:.2f})")
            continue

        # NLP Sentiment Veto
        sentiment = get_news_sentiment(ticker.split('=')[0])
        if direction == 'Long' and sentiment < -0.5:
            log.info(f"Sentiment Veto for {ticker}: Negative News ({sentiment:.2f})")
            continue

        # Correlation Veto
        open_pos = broker.get_open_positions()
        if check_correlation_veto(ticker, direction, open_pos, corr_matrix):
            continue

        # 6. Execution & Position Sizing
        balance = broker.get_account_balance()
        atr = current_atrs[ticker]
        entry_price = current_prices[ticker]

        # Calculate Kelly Size (assuming 50% win rate for first trades)
        lot_size = calculate_kelly_size(balance, atr, entry_price, 0.55, 2.0, -1.0)

        if lot_size <= 0:
            continue

        # Apply Slippage and Spread
        adj_entry, cost = execute_cost_model(ticker, entry_price, atr, atr, direction)

        if direction == 'Long':
            sl = adj_entry - (1.5 * atr)
            tp = adj_entry + (3.0 * atr)
        else:
            sl = adj_entry + (1.5 * atr)
            tp = adj_entry - (3.0 * atr)

        broker.place_market_order(ticker, direction, lot_size, adj_entry, sl, tp, cost)

        send_message(f"🚨 YENİ SİNYAL: {ticker} {direction}\nGiriş: {adj_entry:.4f}\nSL: {sl:.4f}\nTP: {tp:.4f}\nLot: {lot_size:.4f}")

    # Memory cleanup
    del dfs_htf
    del dfs_ltf
    gc.collect()

def telegram_polling():
    # Setup simple telebot polling in background thread if needed
    # For now we mock the handling of commands via simple loops or webhooks
    pass

if __name__ == "__main__":
    log.info("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")
    send_message("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")

    # Train initial ML Model
    try:
        df_train = fetch_data('GC=F', '1d', '5y')
        df_train = add_features(df_train)
        train_model(df_train)
    except Exception as e:
        log.error(f"Initial ML training failed: {e}")

    schedule.every().hour.at(":00").do(run_live_cycle)

    # Daily Heartbeat
    schedule.every().day.at("08:00").do(lambda: send_message("🟢 Sistem Aktif: Son 24 saat döngüsü tamamlandı. Kasa: $" + str(broker.get_account_balance())))

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)

    except KeyboardInterrupt:
        log.info("System Shutting Down...")
        send_message("Sistem kapatıldı.")

