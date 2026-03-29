import schedule
import time
import pandas as pd
import gc
from typing import Dict, Any, List

# Core modules
from ed_quant_engine.logger import log
from ed_quant_engine.config import UNIVERSE, INITIAL_CAPITAL
from ed_quant_engine.broker import PaperBroker

# Data & Features
from ed_quant_engine.data_loader import fetch_universe_data
from ed_quant_engine.features import add_features, align_mtf_data

# Strategy & Risk
from ed_quant_engine.macro_filter import fetch_macro_data, detect_black_swan, detect_flash_crash, get_market_regime
from ed_quant_engine.sentiment_filter import fetch_rss_news, sentiment_veto
from ed_quant_engine.ml_validator import validate_signal
from ed_quant_engine.strategy import generate_signals
from ed_quant_engine.portfolio_manager import calculate_correlation_matrix, correlation_veto, check_global_limits, calculate_fractional_kelly

# Notifications & Telegram
from ed_quant_engine.notifier import send_trade_alert, send_critical_alert, send_telegram_message, send_heartbeat
from ed_quant_engine.telegram_listener import start_telegram_listener, bot_controller

# Reporting
from ed_quant_engine.reporter import generate_tear_sheet
from ed_quant_engine.paper_db import get_all_closed_trades

class QuantEngine:
    def __init__(self):
        self.broker = PaperBroker(initial_capital=INITIAL_CAPITAL)
        self.cycle_count = 0
        self.error_count = 0
        self.rss_news = []
        log.info("ED Capital Quant Engine Initialized.")

    def fetch_latest_news(self):
        """Runs every hour to keep sentiment cache updated."""
        try:
            self.rss_news = fetch_rss_news()
            log.info("RSS News Sentiment Updated.")
        except Exception as e:
            log.error(f"Failed to update RSS news: {e}")
            self.error_count += 1

    def manage_open_positions(self, universe_data: Dict[str, Dict[str, pd.DataFrame]], black_swan_active: bool):
        """Checks Stop Loss, Take Profit, and Trailing Stops. Closes positions aggressively if Black Swan."""
        open_positions = self.broker.get_open_positions()

        for trade in open_positions:
            ticker = trade['ticker']
            trade_id = trade['trade_id']
            direction = trade['direction']

            # Get latest price for the ticker
            if ticker not in universe_data or '1h' not in universe_data[ticker] or universe_data[ticker]['1h'].empty:
                continue

            latest_bar = universe_data[ticker]['1h'].iloc[-1]
            current_price = latest_bar['Close']

            # Check Flash Crash Anomaly per asset
            flash_crash_active = detect_flash_crash(universe_data[ticker]['1h'])

            # Emergency Exit Protocol (Black Swan or Flash Crash)
            if black_swan_active or flash_crash_active:
                log.critical(f"EMERGENCY EXIT triggered for {ticker}")
                pnl = (current_price - trade['entry_price']) if direction == 'Long' else (trade['entry_price'] - current_price)
                self.broker.close_position(trade_id, current_price, pnl)
                send_telegram_message(f"🚨 <b>ACİL ÇIKIŞ</b> 🚨\nVarlık: {ticker}\nKâr/Zarar: ${pnl:.2f}\nGerekçe: {'VIX Şoku' if black_swan_active else 'Z-Score Flaş Çöküş'}")
                continue

            # Standard Exit Checks (TP / SL)
            hit_sl = (direction == 'Long' and current_price <= trade['sl_price']) or (direction == 'Short' and current_price >= trade['sl_price'])
            hit_tp = (direction == 'Long' and current_price >= trade['tp_price']) or (direction == 'Short' and current_price <= trade['tp_price'])

            if hit_sl or hit_tp:
                exit_reason = "TP" if hit_tp else "SL"
                pnl = (current_price - trade['entry_price']) if direction == 'Long' else (trade['entry_price'] - current_price)

                # Assume closed exactly at TP/SL price instead of Close for paper realism, unless slipped past it
                exit_price = trade['tp_price'] if hit_tp else trade['sl_price']

                self.broker.close_position(trade_id, exit_price, pnl)
                send_telegram_message(f"🔔 <b>İŞLEM KAPANDI ({exit_reason})</b>\nVarlık: {ticker}\nÇıkış Fiyatı: {exit_price:.4f}\nNet Kâr/Zarar: ${pnl:.2f}")
                continue

            # Trailing Stop & Breakeven Management (Phase 12)
            # 1. Breakeven
            breakeven_trigger = abs(trade['entry_price'] - trade['sl_price']) * 0.5 # 50% of initial risk

            if direction == 'Long' and (current_price - trade['entry_price']) >= breakeven_trigger:
                if trade['sl_price'] < trade['entry_price']: # Strictly monotonic check
                    self.broker.modify_trailing_stop(trade_id, trade['entry_price'])
                    send_telegram_message(f"🔒 <b>RİSK SIFIRLANDI</b>\nVarlık: {ticker} SL seviyesi Giriş Fiyatına (Başa Baş) çekildi.")
                    trade['sl_price'] = trade['entry_price'] # Update local state for Trailing stop check next

            elif direction == 'Short' and (trade['entry_price'] - current_price) >= breakeven_trigger:
                if trade['sl_price'] > trade['entry_price']:
                    self.broker.modify_trailing_stop(trade_id, trade['entry_price'])
                    send_telegram_message(f"🔒 <b>RİSK SIFIRLANDI</b>\nVarlık: {ticker} SL seviyesi Giriş Fiyatına (Başa Baş) çekildi.")
                    trade['sl_price'] = trade['entry_price']

            # 2. Dynamic Trailing Stop (Based on ATR calculated previously, simplified here using distance)
            current_atr = latest_bar['ATRr_14'] if 'ATRr_14' in latest_bar else (current_price * 0.01)
            trail_dist = current_atr * 1.5

            if direction == 'Long':
                new_sl = current_price - trail_dist
                if new_sl > trade['sl_price']: # Strictly monotonic
                    self.broker.modify_trailing_stop(trade_id, new_sl)
                    log.info(f"[{ticker}] Trailing Stop moved UP to {new_sl:.4f}")
            elif direction == 'Short':
                new_sl = current_price + trail_dist
                if new_sl < trade['sl_price']: # Strictly monotonic
                    self.broker.modify_trailing_stop(trade_id, new_sl)
                    log.info(f"[{ticker}] Trailing Stop moved DOWN to {new_sl:.4f}")

    def run_live_cycle(self):
        """The main Orchestration Loop."""
        log.info(f"--- Starting Live Cycle #{self.cycle_count + 1} ---")

        # 0. Check Manual Overrides
        if bot_controller.panic_close:
            log.critical("Telegram PANIC CLOSE activated. Closing all positions and halting.")
            open_positions = self.broker.get_open_positions()
            for t in open_positions:
                 self.broker.close_position(t['trade_id'], t['entry_price'], 0) # Close at BreakEven logic placeholder
                 send_critical_alert(f"PANİK BUTONU: {t['ticker']} Kapatıldı.")
            bot_controller.panic_close = False
            bot_controller.is_paused = True # Auto-pause after panic
            return

        # 1. Macro Filters & Circuit Breakers (Phase 6, 19)
        macro_df = fetch_macro_data()
        black_swan_active = detect_black_swan(macro_df)
        market_regime = get_market_regime(macro_df)
        log.info(f"Market Regime: {market_regime}. Black Swan: {black_swan_active}")

        if black_swan_active:
            send_critical_alert("VIX Devre Kesici Tetiklendi! Sistem Savunma Moduna Geçti. Yeni İşlemler Durduruldu.")

        # 2. Fetch MTF Universe Data
        try:
            universe_data = fetch_universe_data(UNIVERSE, ['1d', '1h'])
        except Exception as e:
            log.error(f"Data Fetch Pipeline failed: {e}")
            self.error_count += 1
            return

        # 3. Correlation Engine Update
        corr_matrix = calculate_correlation_matrix(universe_data)

        # 4. Process MTF Features (Zero Lookahead Bias Pipeline)
        processed_data = {}
        for ticker, dfs in universe_data.items():
            if '1d' in dfs and '1h' in dfs:
                df_1d_feat = add_features(dfs['1d'])
                df_1h_feat = add_features(dfs['1h'])
                df_mtf = align_mtf_data(df_1d_feat, df_1h_feat)

                if df_mtf is not None and not df_mtf.empty:
                    processed_data[ticker] = df_mtf
                    # Re-assign back to universe_data for manage_open_positions ATR lookup
                    universe_data[ticker]['1h'] = df_mtf

        # 5. Manage Open Positions (TP, SL, Breakeven, Flash Crash Exits)
        self.manage_open_positions(universe_data, black_swan_active)

        # Skip scanning if manually paused or in Black Swan regime
        if bot_controller.is_paused:
            log.info("System Paused. Skipping scan phase.")
            return

        if black_swan_active:
             log.warning("Black Swan Active. Skipping scan phase.")
             return

        # 6. Global Portfolio Limits Check
        current_capital = self.broker.get_account_balance()
        open_positions = self.broker.get_open_positions()

        if check_global_limits(open_positions, current_capital):
            log.warning("Global limits reached. Skipping new signal generation.")
            return

        # Calculate fractional Kelly risk multiplier
        closed_trades = get_all_closed_trades()
        kelly_fraction = calculate_fractional_kelly(closed_trades)

        # 7. Scan for New Signals
        for ticker, df_mtf in processed_data.items():

            # Check Flash Crash anomaly again just in case
            if detect_flash_crash(df_mtf):
                log.warning(f"Flash crash detected in {ticker}. Skipping signal gen.")
                continue

            # Strategy MTF Confluence Check
            signal = generate_signals(df_mtf, ticker, current_capital, risk_fraction=kelly_fraction)

            if signal:
                direction = signal['direction']

                # 8. VETO GATES
                # Gate 1: Correlation Veto
                if correlation_veto(ticker, direction, corr_matrix, open_positions):
                    continue

                # Gate 2: Machine Learning Veto (Probability Check)
                if not validate_signal(ticker, df_mtf, direction):
                    continue

                # Gate 3: NLP Sentiment Veto
                if sentiment_veto(ticker, direction, self.rss_news):
                    continue

                # Gate 4: Macro Regime Context Veto
                if market_regime == "Risk-Off" and ticker in UNIVERSE["metals"] and direction == "Long":
                    log.info(f"Macro Veto: {ticker} Long rejected due to Risk-Off regime (Strong DXY/Yields).")
                    continue
                if market_regime == "Risk-On" and ticker in UNIVERSE["forex_try"] and direction == "Long":
                    log.info(f"Macro Veto: {ticker} Long rejected due to Risk-On regime (Weak Dollar expected).")
                    continue

                # 9. Execution
                log.info(f"ALL VETOS CLEARED. EXECUTING {direction} {ticker}")
                trade_id = self.broker.place_market_order(signal)
                send_trade_alert(signal)

                # Update open_positions list so limits hit immediately for next ticker in loop
                open_positions = self.broker.get_open_positions()
                if check_global_limits(open_positions, current_capital):
                    log.warning("Global limits reached mid-scan. Halting further execution.")
                    break

        self.cycle_count += 1

        # Memory Cleanup (Garbage Collection)
        del processed_data
        del universe_data
        del macro_df
        del corr_matrix
        gc.collect()
        log.info("Live cycle finished. Memory cleaned.")

    def run_daily_heartbeat(self):
        """Sends daily 08:00 status report."""
        open_trades = len(self.broker.get_open_positions())
        send_heartbeat(self.cycle_count, self.error_count, open_trades)
        # Reset counters
        self.cycle_count = 0
        self.error_count = 0

    def run_weekly_report(self):
        """Generates Tear Sheet HTML/PDF every Friday."""
        log.info("Generating Weekly Tear Sheet...")
        generate_tear_sheet()

def start_engine():
    # Start Telegram Listener Thread
    start_telegram_listener()

    engine = QuantEngine()

    # Startup Message & State Recovery
    current_cap = engine.broker.get_account_balance()
    open_pos = len(engine.broker.get_open_positions())
    send_telegram_message(f"🚀 <b>ED Capital Quant Engine Canlı Modda Başlatıldı.</b>\nKasa: ${current_cap:,.2f}\nAçık Pozisyonlar: {open_pos}\n\n<i>Önceki durum başarıyla hafızaya alındı.</i>")

    # Initial data pull for sentiment
    engine.fetch_latest_news()

    # Schedule tasks based on exact Candle-Close Synchronization (Phase 23)
    # E.g., Hourly candles close exactly at the top of the hour. Run at XX:01
    schedule.every().hour.at(":01").do(engine.run_live_cycle)

    # Run sentiment check every hour at minute 50
    schedule.every().hour.at(":50").do(engine.fetch_latest_news)

    # Daily Heartbeat at 08:00
    schedule.every().day.at("08:00").do(engine.run_daily_heartbeat)

    # Weekly Report Friday at Market Close (e.g. 23:05)
    schedule.every().friday.at("23:05").do(engine.run_weekly_report)

    # Initial test run
    log.info("Executing initial startup cycle...")
    engine.run_live_cycle()

    log.info("Scheduler loop started. Waiting for top of the hour...")
    while True:
        try:
            # Check if Telegram command forced a scan
            if bot_controller.force_scan:
                log.info("Manual Force Scan triggered via Telegram.")
                engine.run_live_cycle()
                bot_controller.force_scan = False

            schedule.run_pending()
            time.sleep(1)
        except Exception as e:
            log.critical(f"FATAL ERROR IN MAIN LOOP: {e}")
            send_critical_alert(f"Ana döngü çöktü! Hata: {e}")
            time.sleep(60) # Prevent rapid crash loops

if __name__ == "__main__":
    start_engine()
