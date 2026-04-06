import asyncio
import schedule
import gc
import os
from typing import Dict, Any
import pandas as pd

from broker import PaperBroker
from data_loader import fetch_live_data
from features import add_features
from strategy import generate_signals, update_trailing_stop
from filters.portfolio_manager import calculate_correlation_matrix, check_correlation_veto, check_global_exposure, calculate_kelly_position_size
from filters.macro_filter import get_macro_regime, check_vix_circuit_breaker
from filters.ml_validator import validate_signal_with_ml, ensure_ml_model
from filters.sentiment_filter import check_sentiment_veto, analyze_news_sentiment
from utils.notifier import send_telegram_message, send_telegram_document, BOT_TOKEN, ADMIN_CHAT_ID
from utils.reporter import generate_tear_sheet
from utils.logger import setup_logger

logger = setup_logger("MainEngine")

# Initialize Broker (Abstraction Layer)
broker = PaperBroker()

# TICKER UNIVERSE (Phase 1 Extracted)
TICKERS = [
    "GC=F", "SI=F", "HG=F", "PA=F", "PL=F",
    "CL=F", "BZ=F", "NG=F",
    "ZW=F", "ZC=F", "ZS=F", "KC=F", "CC=F", "SB=F", "CT=F",
    "USDTRY=X", "EURTRY=X", "GBPTRY=X", "JPYTRY=X", "CNHY=X"
]

system_paused = False

def get_dynamic_kelly_metrics():
    """Phase 15: Calculates real-time Win Rate and Avg Win/Loss from PaperBroker (via SQLite)."""
    import paper_db
    df_closed = paper_db.get_closed_trades()
    if df_closed.empty or len(df_closed) < 10:
        return 0.55, 150.0, 100.0

    wins = df_closed[df_closed['pnl'] > 0]
    losses = df_closed[df_closed['pnl'] <= 0]

    win_rate = len(wins) / len(df_closed)
    avg_win = wins['pnl'].mean() if not wins.empty else 100.0
    avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 100.0

    return win_rate, avg_win, avg_loss

async def check_open_positions_task():
    """Phase 5 & Phase 12: Manages existing trades, triggers exits and updates trailing stops."""
    try:
        positions = broker.get_open_positions()
        if not positions:
            return

        for pos in positions:
            ticker = pos['ticker']
            df = await fetch_live_data(ticker, interval="1h")
            if df.empty:
                continue

            current_price = df['Close'].iloc[-1]
            trade_id = pos['trade_id']
            direction = pos['direction']
            sl = pos['sl_price']
            tp = pos['tp_price']
            entry = pos['entry_price']

            # Check if hit SL or TP
            if (direction == "Long" and (current_price <= sl or current_price >= tp)) or \
               (direction == "Short" and (current_price >= sl or current_price <= tp)):

                broker.close_position(trade_id, current_price, atr=0.0) # Simplify ATR for closing here
                await send_telegram_message(f"🚨 İşlem Kapandı [{ticker}]: Fiyat {current_price:.4f} seviyesine ulaştı.")
                continue

            # Phase 12: Breakeven & Trailing Stop logic
            # Simplified Trailing Stop using raw calculation from strategy
            features_df = add_features(df)
            if not features_df.empty:
                atr = features_df['ATRr_14'].iloc[-1]
                new_sl = update_trailing_stop(current_price, sl, direction, atr)
                if new_sl:
                    broker.modify_trailing_stop(trade_id, new_sl)
    except Exception as e:
        logger.error(f"Error checking open positions: {e}")


async def run_live_cycle():
    """Phase 16 & 23: Main Multi-Timeframe (MTF) Pipeline Orchestrator."""
    global system_paused
    if system_paused:
        logger.info("Sistem duraklatıldı. Tarama atlanıyor.")
        return

    logger.info("Canlı Piyasa Döngüsü (MTF) Başladı...")

    # Always check open positions to manage them even if we don't open new ones.
    await check_open_positions_task()

    # Phase 19: VIX Circuit Breaker
    if await check_vix_circuit_breaker():
        logger.warning("VIX Devre Kesici Aktif. Tarama İptal.")
        return

    # Phase 11: Global Exposure
    if check_global_exposure(max_positions=3):
        return

    # Phase 6: Macro Regime
    macro_regime = await get_macro_regime()
    logger.info(f"Mevcut Makro Rejim: {macro_regime}")

    prices_dict = {}
    htf_dfs = {}
    ltf_dfs = {}

    for ticker in TICKERS:
        htf = await fetch_live_data(ticker, interval="1d")
        ltf = await fetch_live_data(ticker, interval="1h")
        if htf.empty or ltf.empty: continue
        htf_dfs[ticker] = htf
        ltf_dfs[ticker] = ltf
        prices_dict[ticker] = ltf['Close']

    if not prices_dict: return

    # Phase 11: Correlation Engine
    corr_matrix = calculate_correlation_matrix(prices_dict)

    # Phase 15: Get Dynamic Kelly Metrics
    win_rate, avg_win, avg_loss = get_dynamic_kelly_metrics()

    for ticker in TICKERS:
        if ticker not in htf_dfs or ticker not in ltf_dfs: continue

        htf_df = add_features(htf_dfs[ticker])
        ltf_df = ltf_dfs[ticker]
        if htf_df.empty or ltf_df.empty: continue

        # Phase 16: MTF Alignment avoiding Lookahead Bias
        htf_shifted = htf_df.shift(1).reset_index()
        ltf_df_reset = ltf_df.reset_index()

        # Strip timezones
        if htf_shifted['Date'].dt.tz is not None: htf_shifted['Date'] = htf_shifted['Date'].dt.tz_localize(None)
        if ltf_df_reset['Datetime'].dt.tz is not None: ltf_df_reset['Datetime'] = ltf_df_reset['Datetime'].dt.tz_localize(None)

        merged_df = pd.merge_asof(
            ltf_df_reset.sort_values('Datetime'),
            htf_shifted.sort_values('Date'),
            left_on='Datetime',
            right_on='Date',
            direction='backward',
            suffixes=('', '_HTF')
        )
        merged_df.set_index('Datetime', inplace=True)

        signal = generate_signals(merged_df, ticker)

        if signal:
            direction = signal['direction']
            raw_entry = signal['entry_price']

            # MTF Veto
            if 'EMA_50_HTF' in merged_df.columns:
                htf_ema = merged_df['EMA_50_HTF'].iloc[-1]
                htf_close = merged_df['Close_HTF'].iloc[-1]
                if direction == "Long" and htf_close < htf_ema: continue
                if direction == "Short" and htf_close > htf_ema: continue

            # Correlation Veto
            if check_correlation_veto(ticker, direction, corr_matrix): continue

            # Macro Veto
            if direction == "Long" and ticker in ["GC=F", "SI=F"] and macro_regime == "Risk-Off": continue

            # ML Veto
            ltf_features = add_features(ltf_df)
            if ltf_features.empty: continue
            if not validate_signal_with_ml(ltf_features.iloc[-1]): continue

            # NLP Veto
            sentiment_analyzer = analyze_news_sentiment()
            if check_sentiment_veto(ticker, direction, sentiment_analyzer): continue

            # Phase 15: Dynamic Kelly Sizing
            balance = broker.get_account_balance()
            lot_size = calculate_kelly_position_size(
                ticker=ticker, entry=raw_entry, stop_loss=signal['sl_price'],
                balance=balance, win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss
            )

            if lot_size <= 0: continue

            # Phase 21 & 24: Execution via Broker
            receipt = broker.place_market_order(
                ticker=ticker, direction=direction, qty=lot_size,
                current_price=raw_entry, sl=signal['sl_price'], tp=signal['tp_price'], atr=signal['atr']
            )

            if receipt:
                import paper_db
                trades = paper_db.get_open_trades()
                executed_price = raw_entry # Fallback
                for t in trades:
                    if t['trade_id'] == receipt: executed_price = t['entry_price']

                await send_telegram_message(
                    f"🚨 YÜKSEK GÜVENİLİRLİKLİ SİNYAL UYGULANDI (MTF/ML/NLP) 🚨\n\n"
                    f"Varlık: {ticker}\n"
                    f"Yön: {direction}\n"
                    f"Giriş: {executed_price:.4f}\n"
                    f"SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}\n"
                    f"Lot: {lot_size:.4f}\n"
                    f"Kelly Metrics: Win %{win_rate*100:.1f}"
                )

    # Garbage Collection
    del htf_dfs, ltf_dfs, prices_dict, corr_matrix
    gc.collect()
    logger.info("Döngü tamamlandı, Garbage Collection çalıştırıldı.")

async def send_weekly_report():
    """Phase 13: Generates and sends the weekly tear sheet."""
    logger.info("Haftalık Rapor Üretiliyor...")
    report_path = generate_tear_sheet(initial_balance=float(os.getenv("INITIAL_BALANCE", "10000.0")))
    if report_path:
        await send_telegram_document(report_path, caption="📊 ED Capital Quant Engine - Piyasalara Genel Bakış")

# --- TELEGRAM BOT INTERFACE (Phase 17) ---
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

def check_admin(update: Update) -> bool:
    if str(update.effective_chat.id) != ADMIN_CHAT_ID:
        logger.critical(f"YETKİSİZ ERİŞİM! User ID: {update.effective_chat.id}")
        return False
    return True

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_admin(update): return
    balance = broker.get_account_balance()
    positions = broker.get_open_positions()
    msg = f"🟢 <b>Sistem Durumu</b>\n\nGüncel Bakiye: ${balance:,.2f}\nDuraklatıldı: {'Evet' if system_paused else 'Hayır'}\n\nAçık Pozisyonlar ({len(positions)}):\n"
    for pos in positions: msg += f"- {pos['direction']} {pos['ticker']} @ {pos['entry_price']:.4f} (Lot: {pos['position_size']:.2f})\n"
    await update.message.reply_text(msg, parse_mode='HTML')

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_admin(update): return
    global system_paused
    system_paused = True
    await update.message.reply_text("⏸ Sistem yeni sinyal aramayı durdurdu. Açık pozisyonlar izleniyor.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_admin(update): return
    global system_paused
    system_paused = False
    await update.message.reply_text("▶️ Sistem otonom tarama moduna geri döndü.")

async def cmd_panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_admin(update): return
    positions = broker.get_open_positions()
    if not positions:
        await update.message.reply_text("Kapatılacak açık pozisyon yok.")
        return
    for pos in positions:
        df = await fetch_live_data(pos['ticker'], interval="1h")
        if df.empty: continue
        current_price = df['Close'].iloc[-1]
        broker.close_position(pos['trade_id'], current_price, atr=0.0) # Using 0.0 ATR for simplicity in panic mode
    await update.message.reply_text("🚨 PANİK ÇIKIŞI TAMAMLANDI. Bütün pozisyonlar anlık fiyattan kapatıldı.")

async def cmd_force_scan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not check_admin(update): return
    await update.message.reply_text("🔍 Zorunlu (Force) Tarama başlatılıyor...")
    asyncio.create_task(run_live_cycle())

async def run_telegram_bot_task():
    """Starts the telegram bot inside the existing asyncio loop."""
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN eksik. Telegram Bot başlatılamadı.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("durum", cmd_status))
    app.add_handler(CommandHandler("durdur", cmd_pause))
    app.add_handler(CommandHandler("devam", cmd_resume))
    app.add_handler(CommandHandler("kapat_hepsi", cmd_panic))
    app.add_handler(CommandHandler("tara", cmd_force_scan))

    logger.info("Telegram İki Yönlü Komut Dinleyicisi Başlatıldı.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

# --- DAEMON SCHEDULER ---

def run_async_task(task_func):
    asyncio.create_task(task_func())

async def main_loop():
    logger.info("ED Capital Quant Engine Başlatılıyor...")
    await ensure_ml_model()

    # Telegram non-blocking
    asyncio.create_task(run_telegram_bot_task())

    balance = broker.get_account_balance()
    await send_telegram_message(f"🚀 ED Capital Quant Engine Canlı Modda Başlatıldı.\nGüncel Portföy: ${balance:,.2f}")

    # Synchronize execution strictly at the start of the hour
    schedule.every().hour.at(":01").do(run_async_task, run_live_cycle)
    # schedule.every(5).minutes.do(run_async_task, check_open_positions_task) # Managed inside run_live_cycle
    schedule.every().friday.at("23:30").do(run_async_task, send_weekly_report)

    def trigger_retrain(): asyncio.create_task(ensure_ml_model())
    schedule.every().sunday.at("02:00").do(trigger_retrain)

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_loop())
    except KeyboardInterrupt:
        logger.warning("Bot manuel olarak durduruldu.")
    except Exception as e:
        logger.critical(f"Sistem Çöktü: {str(e)}")
