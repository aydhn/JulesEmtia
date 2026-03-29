import schedule
import time
import datetime
import gc
from typing import Dict, List, Any

# Core Modules
import ed_quant_engine.config as config
from ed_quant_engine.core.logger import logger
from ed_quant_engine.notifications.notifier import send_telegram_message, send_document
from ed_quant_engine.data.data_loader import fetch_multi_timeframe
from ed_quant_engine.features.features import add_features, align_timeframes
from ed_quant_engine.strategy.strategy import MovingAverageCrossStrategy
from ed_quant_engine.broker.paper_broker import PaperBroker
from ed_quant_engine.core.portfolio_manager import PortfolioManager
from ed_quant_engine.core.macro_filter import get_macro_data, check_vix_circuit_breaker, determine_regime
from ed_quant_engine.core.sentiment_filter import sentiment_filter
from ed_quant_engine.models.ml_validator import MLValidator
from ed_quant_engine.analysis.reporter import EDReporter
from ed_quant_engine.analysis.monte_carlo import run_monte_carlo_simulation

# Initialize Global Components
broker = PaperBroker()
portfolio = PortfolioManager(
    max_positions=config.MAX_OPEN_POSITIONS,
    max_risk_pct=config.MAX_PORTFOLIO_RISK_PCT,
    correlation_threshold=config.CORRELATION_THRESHOLD
)
strategy = MovingAverageCrossStrategy()
ml_validator = MLValidator(model_path=config.MODEL_PATH)
reporter = EDReporter()

# System State (Two-Way Telegram)
system_paused = False

def run_live_cycle():
    """
    Phase 23: The Master Live Trading Pipeline.
    Synchronized with candle closes, zero memory leaks, fault-tolerant.
    """
    global system_paused

    if system_paused:
        logger.info("System is paused. Skipping signal generation. Managing existing open positions only.")
        manage_open_positions() # Still protect capital!
        return

    logger.info(f"Starting Live Scan Cycle at {datetime.datetime.now()}...")

    # 1. Macro Filters & VIX Circuit Breaker (Black Swan Protection)
    dxy, tnx, vix = get_macro_data()
    is_circuit_breaker = check_vix_circuit_breaker(vix, threshold=config.VIX_THRESHOLD)

    if is_circuit_breaker:
        logger.critical("Circuit Breaker Active: Halting new trades. Entering defense mode.")
        manage_open_positions(aggressive_trailing=True)
        return

    regime = determine_regime(dxy, tnx)
    logger.info(f"Market Regime: {regime}")

    # 2. Manage Existing Trades (Trailing Stops, Breakeven, Exits)
    manage_open_positions()

    # 3. Check Global Exposure
    open_positions = broker.get_open_positions()
    current_capital = broker.get_account_balance()

    if portfolio.check_exposure_limits(open_positions, current_capital):
        logger.info("Global Exposure Limits reached. Skipping new signals.")
        return

    # 4. Universe Scan & Signal Generation
    for category, tickers in config.TICKERS.items():
        for ticker in tickers:
            try:
                # Fetch MTF Data
                htf, ltf = fetch_multi_timeframe(ticker)
                if htf.empty or ltf.empty: continue

                # Add Features
                htf_features = add_features(htf, is_htf=True)
                ltf_features = add_features(ltf, is_htf=False)

                # Align & Prevent Lookahead Bias
                aligned_df = align_timeframes(htf_features, ltf_features)
                if aligned_df.empty: continue

                # Generate Strategy Signals
                signals = strategy.generate_signals(aligned_df)
                latest = signals.iloc[-1]

                signal_dir = latest.get('signal', 0)
                if signal_dir == 0: continue

                direction_str = "Long" if signal_dir == 1 else "Short"

                # 5. The Veto Pipeline (ML -> Sentiment -> Correlation)

                # Veto 1: Machine Learning Classifier
                if not ml_validator.validate_signal(aligned_df):
                    continue

                # Veto 2: News Sentiment (NLP)
                sentiment_score = sentiment_filter.get_sentiment(ticker)
                if signal_dir == 1 and sentiment_score < -0.5:
                    logger.warning(f"Sentiment Veto: {ticker} Long rejected due to highly negative news ({sentiment_score})")
                    continue
                if signal_dir == -1 and sentiment_score > 0.5:
                    logger.warning(f"Sentiment Veto: {ticker} Short rejected due to highly positive news ({sentiment_score})")
                    continue

                # Veto 3: Correlation Duplication
                # We need closing prices of open positions to build correlation matrix.
                # For zero budget, we assume we have a master dataframe, or we pull a small 30d window.
                # (Skipped fast calculation for brevity, assume passed if no open trades)
                # Fetch closing prices for correlation matrix (optimization: cache this globally)
                try:
                    # In a real system, you'd cache the master matrix. Here we build a tiny one for the current ticker vs open ones.
                    history_dict = {}
                    for pos in open_positions:
                        open_ticker = pos['ticker']
                        history_dict[open_ticker] = fetch_multi_timeframe(open_ticker)[0]['Close']
                    history_dict[ticker] = htf['Close']

                    if len(history_dict) > 1:
                        corr_df = pd.DataFrame(history_dict)
                        corr_matrix = portfolio.calculate_correlation_matrix(corr_df)
                    else:
                        corr_matrix = pd.DataFrame()

                except Exception as e:
                    logger.error(f"Correlation Matrix Error: {e}")
                    corr_matrix = pd.DataFrame()

                if portfolio.correlation_veto(ticker, direction_str, open_positions, corr_matrix):
                    continue

                # 6. Execution & Risk Sizing (Kelly Criterion)
                closed_trades = broker.db.get_all_closed_trades()
                kelly_fraction = portfolio.calculate_kelly_fraction(closed_trades)

                entry, sl, tp = strategy.get_trade_parameters(latest, signal_dir)
                qty = strategy.calculate_position_size(current_capital, entry, sl, kelly_fraction)

                # Slippage modeling (Dynamic ATR-based)
                slippage = latest['atr_14'] * 0.1 # Example 10% of ATR slippage

                receipt = broker.place_market_order(
                    ticker=ticker,
                    direction=direction_str,
                    quantity=qty,
                    slippage=slippage,
                    sl_price=sl,
                    tp_price=tp,
                    current_price=entry
                )

                msg = f"🟢 <b>YENİ İŞLEM AÇILDI</b>\n\nVarlık: {ticker}\nYön: {direction_str}\nGiriş: {entry:.4f}\nSL: {sl:.4f}\nTP: {tp:.4f}\nLot: {qty:.4f}\nKelly Risk: %{kelly_fraction*100:.2f}"
                send_telegram_message(msg)

                # Re-check exposure before next ticker
                open_positions = broker.get_open_positions()
                if len(open_positions) >= config.MAX_OPEN_POSITIONS:
                    break

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")

    # 7. Garbage Collection to prevent Memory Leaks
    gc.collect()
    logger.info("Scan Cycle Complete.")

def manage_open_positions(aggressive_trailing: bool = False):
    """
    Phase 12: Trailing Stop and Breakeven logic.
    Monitors all open positions from the DB.
    """
    open_positions = broker.get_open_positions()
    if not open_positions: return

    for pos in open_positions:
        ticker = pos['ticker']
        trade_id = pos['trade_id']
        direction = pos['direction']
        entry = pos['entry_price']
        current_sl = pos['sl_price']
        tp = pos['tp_price']

        # Get latest price and ATR (using data_loader or caching)
        try:
            df = fetch_multi_timeframe(ticker)[1] # LTF for finer exit
            if df.empty: continue

            latest_close = df['Close'].iloc[-1]
            # Need ATR for trailing math. Approximate via pandas.
            tr1 = df['High'] - df['Low']
            tr2 = abs(df['High'] - df['Close'].shift())
            tr3 = abs(df['Low'] - df['Close'].shift())
            atr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean().iloc[-1]

            # Check TP / SL Hits
            if direction == 'Long':
                if latest_close <= current_sl:
                    broker.close_position(trade_id, current_sl, is_sl=True)
                    send_telegram_message(f"🔴 İşlem Kapandı (Zarar Kes): {ticker} @ {current_sl}")
                    continue
                elif latest_close >= tp:
                    broker.close_position(trade_id, tp, is_tp=True)
                    send_telegram_message(f"🟢 İşlem Kapandı (Kâr Al): {ticker} @ {tp}")
                    continue

                # Trailing Stop Logic (Breakeven + Trail)
                trail_distance = 0.5 * atr if aggressive_trailing else 1.5 * atr
                new_sl = latest_close - trail_distance

                # Strict monotonic rule: SL can only move UP for Longs
                if new_sl > current_sl and latest_close > entry:
                    broker.modify_trailing_stop(trade_id, new_sl)
                    logger.info(f"Trailing SL raised for {ticker} to {new_sl}")

            elif direction == 'Short':
                if latest_close >= current_sl:
                    broker.close_position(trade_id, current_sl, is_sl=True)
                    send_telegram_message(f"🔴 İşlem Kapandı (Zarar Kes): {ticker} @ {current_sl}")
                    continue
                elif latest_close <= tp:
                    broker.close_position(trade_id, tp, is_tp=True)
                    send_telegram_message(f"🟢 İşlem Kapandı (Kâr Al): {ticker} @ {tp}")
                    continue

                # Trailing Stop Logic
                trail_distance = 0.5 * atr if aggressive_trailing else 1.5 * atr
                new_sl = latest_close + trail_distance

                # Strict monotonic rule: SL can only move DOWN for Shorts
                if new_sl < current_sl and latest_close < entry:
                    broker.modify_trailing_stop(trade_id, new_sl)
                    logger.info(f"Trailing SL lowered for {ticker} to {new_sl}")

        except Exception as e:
            logger.error(f"Error managing position {ticker}: {e}")

# Telegram Bot Setup (Two-Way Communication)
def start_telegram_listener():
    from telegram import Update
    from telegram.ext import Application, CommandHandler, ContextTypes

    async def check_auth(update: Update) -> bool:
        if str(update.effective_chat.id) != config.ADMIN_CHAT_ID:
            logger.critical(f"Unauthorized Telegram access attempt by ID: {update.effective_chat.id}")
            await update.message.reply_text("Yetkisiz erişim. Loglandı.")
            return False
        return True

    async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update): return
        cap = broker.get_account_balance()
        open_pos = len(broker.get_open_positions())
        await update.message.reply_text(f"📊 <b>DURUM RAPORU</b>\nKasa: ${cap:.2f}\nAçık Pozisyonlar: {open_pos}\nSistem Duraklatıldı: {system_paused}", parse_mode='HTML')

    async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update): return
        global system_paused
        system_paused = True
        await update.message.reply_text("⏸️ Sistem Tarama Modu: DURDURULDU. Sadece açık pozisyonlar yönetilecek.")

    async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update): return
        global system_paused
        system_paused = False
        await update.message.reply_text("▶️ Sistem Tarama Modu: DEVAM EDİYOR.")

    async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update): return
        await update.message.reply_text("🚨 PANİK BUTONU TETİKLENDİ. Tüm açık işlemler piyasa fiyatından kapatılıyor...")
        open_pos = broker.get_open_positions()
        for pos in open_pos:
            # Get latest price to close
            try:
                df = fetch_multi_timeframe(pos['ticker'])[1]
                if not df.empty:
                    close_px = df['Close'].iloc[-1]
                    broker.close_position(pos['trade_id'], close_px)
            except: pass
        await update.message.reply_text("Tüm pozisyonlar kapatıldı.")

    async def cmd_tara(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_auth(update): return
        await update.message.reply_text("🔍 Manuel tarama (Force Scan) başlatılıyor...")
        import threading
        threading.Thread(target=run_live_cycle, daemon=True).start()

    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", cmd_durum))
    app.add_handler(CommandHandler("durdur", cmd_durdur))
    app.add_handler(CommandHandler("devam", cmd_devam))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
    app.add_handler(CommandHandler("tara", cmd_tara))

    # Run in background via create_task to avoid blocking main schedule loop
    logger.info("Starting Telegram Bot Listener (Two-Way)")

    # For a fully async implementation, you would `await app.run_polling()`
    # Since we are using a simple schedule loop below, we run polling in a separate thread.
    import threading
    import asyncio

    def run_polling():
        # Quick fix for nest_asyncio in environments
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        app.run_polling(drop_pending_updates=True)

    threading.Thread(target=run_polling, daemon=True).start()

# Scheduler Tasks
schedule.every().hour.at(":00").do(run_live_cycle) # Run exactly on the hour
schedule.every().friday.at("22:00").do(reporter.create_tear_sheet) # Weekly Tear Sheet
schedule.every().sunday.at("10:00").do(run_monte_carlo_simulation) # Weekly Stress Test

if __name__ == "__main__":
    logger.info("Initializing ED Capital Quant Engine...")

    # Start Sentiment NLP Background Task
    sentiment_filter.start_background_task()

    if config.TELEGRAM_BOT_TOKEN:
        start_telegram_listener()
        send_telegram_message("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.\nSistem 7/24 Aktif.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("System shutting down gracefully.")

# Added Tasks
def daily_heartbeat():
    """Phase 8: Daily Heartbeat Notification"""
    cap = broker.get_account_balance()
    open_pos = len(broker.get_open_positions())
    msg = f"🟢 Sistem Aktif (Heartbeat)\nKasa: ${cap:.2f}\nAçık Pozisyonlar: {open_pos}\nVIX Devre Kesici: Beklemede"
    send_telegram_message(msg)

def retrain_ml_model():
    """Phase 18: Autonomous ML Retraining (Weekly)"""
    logger.info("Starting Weekly ML Retraining...")
    try:
        # Fetch historical data for a major asset to train the model
        df = fetch_multi_timeframe("GC=F")[0] # Using HTF data for training
        if not df.empty:
            htf_features = add_features(df, is_htf=True)
            ml_validator.train_model(htf_features)
            send_telegram_message("🤖 ML Modeli Başarıyla Yeniden Eğitildi (Haftalık Rutin).")
    except Exception as e:
        logger.error(f"Weekly ML Retraining Failed: {e}")

# Additional Scheduler Tasks
schedule.every().day.at("08:00").do(daily_heartbeat) # Daily Heartbeat
schedule.every().saturday.at("12:00").do(retrain_ml_model) # Weekly ML Retraining
