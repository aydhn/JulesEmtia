import asyncio
import schedule
import time
from datetime import datetime
import gc
import os
import pandas as pd
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Internal Modules
from data_loader import fetch_live_data, fetch_historical_data
from strategy import generate_signals, update_trailing_stop
from paper_broker import PaperBroker
from paper_db import get_closed_trades
from notifier import send_telegram_message, send_telegram_document
from logger import setup_logger
from macro_filter import get_macro_regime, check_vix_circuit_breaker, check_z_score_anomaly
from portfolio_manager import calculate_correlation_matrix, check_correlation_veto, check_global_exposure, calculate_kelly_position_size
from sentiment_filter import SentimentAnalyzer, check_sentiment_veto
from ml_validator import validate_signal_with_ml, train_and_save_model
from features import add_features
from reporter import generate_tear_sheet
from execution_model import calculate_slippage_and_spread

logger = setup_logger("MainOrchestrator")

# Environment & Globals
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
TICKERS = ["GC=F", "SI=F", "CL=F", "USDTRY=X", "EURTRY=X"]
broker = PaperBroker()
sentiment_analyzer = SentimentAnalyzer()
system_paused = False

async def ensure_ml_model():
    if not os.path.exists("rf_model.pkl"):
        logger.info("ML Modeli bulunamadı. Eğitim başlatılıyor...")
        df = await fetch_historical_data("GC=F", period="2y", interval="1d")
        train_and_save_model(df, "GC=F")

async def check_open_positions_task():
    """Phase 12: Trailing Stop and Position Management"""
    positions = broker.get_open_positions()
    if not positions: return

    for pos in positions:
        ticker = pos['ticker']
        trade_id = pos['trade_id']
        direction = pos['direction']
        entry_price = pos['entry_price']
        sl = pos['sl_price']
        tp = pos['tp_price']
        size = pos['position_size']

        df = await fetch_live_data(ticker, interval="1h")
        if df.empty: continue

        df_feat = add_features(df)
        if df_feat.empty: continue

        current_price = df_feat['Close'].iloc[-1]
        atr = df_feat['ATRr_14'].iloc[-1]

        # Phase 19: Check Flash Crash Anomaly
        if check_z_score_anomaly(df_feat['Close']):
            logger.critical(f"Flaş Çöküş! {ticker} işlemi acil kapatılıyor.")
            broker.close_position(str(trade_id), current_price, 0, 0) # Close at market
            continue

        # Phase 12: Breakeven & Trailing Stop Logic
        if direction == "Long":
            # Breakeven
            if current_price > entry_price + (1.5 * atr) and sl < entry_price:
                broker.modify_trailing_stop(str(trade_id), entry_price)
                await send_telegram_message(f"🔒 Risk Sıfırlandı (Breakeven): {ticker} SL seviyesi giriş fiyatına çekildi.")

            # Trailing Stop
            new_sl = update_trailing_stop(current_price, sl, direction, atr)
            if new_sl:
                broker.modify_trailing_stop(str(trade_id), new_sl)
                logger.info(f"Trailing Stop Güncellendi: {ticker} -> {new_sl:.4f}")

        elif direction == "Short":
            if current_price < entry_price - (1.5 * atr) and sl > entry_price:
                broker.modify_trailing_stop(str(trade_id), entry_price)
                await send_telegram_message(f"🔒 Risk Sıfırlandı (Breakeven): {ticker} SL seviyesi giriş fiyatına çekildi.")

            new_sl = update_trailing_stop(current_price, sl, direction, atr)
            if new_sl:
                broker.modify_trailing_stop(str(trade_id), new_sl)
                logger.info(f"Trailing Stop Güncellendi: {ticker} -> {new_sl:.4f}")

        # TP / SL Check
        if (direction == "Long" and (current_price <= sl or current_price >= tp)) or \
           (direction == "Short" and (current_price >= sl or current_price <= tp)):

            # Calculate execution cost for exit
            execution_cost = calculate_slippage_and_spread(ticker, current_price, atr)
            exit_price = current_price - execution_cost if direction == "Long" else current_price + execution_cost

            net_pnl = (exit_price - entry_price) * size if direction == "Long" else (entry_price - exit_price) * size
            net_pnl_pct = (net_pnl / (entry_price * size)) * 100

            broker.close_position(str(trade_id), exit_price, net_pnl, net_pnl_pct)
            await send_telegram_message(f"🔔 İşlem Kapandı: {direction} {ticker} @ {exit_price:.4f}\nNet Kar/Zarar: ${net_pnl:.2f} (%{net_pnl_pct:.2f})")

def get_dynamic_kelly_metrics():
    """Phase 15: Fetch historical win rate, avg win, avg loss for dynamic Kelly Sizing."""
    df_closed = get_closed_trades()
    if df_closed.empty or len(df_closed) < 10:
        # Default conservative metrics if not enough history
        return 0.55, 150.0, 100.0

    wins = df_closed[df_closed['pnl'] > 0]
    losses = df_closed[df_closed['pnl'] <= 0]

    win_rate = len(wins) / len(df_closed)
    avg_win = wins['pnl'].mean() if not wins.empty else 100.0
    avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 100.0

    return win_rate, avg_win, avg_loss

async def run_live_cycle():
    """Phase 16 & 23: Main Multi-Timeframe (MTF) Pipeline Orchestrator."""
    global system_paused
    if system_paused:
        logger.info("Sistem duraklatıldı. Tarama atlanıyor.")
        return

    logger.info("Canlı Piyasa Döngüsü (MTF) Başladı...")

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
            if check_sentiment_veto(ticker, direction, sentiment_analyzer): continue

            # Phase 21: Execution Model
            execution_cost = calculate_slippage_and_spread(ticker, raw_entry, signal['atr'])
            final_entry = raw_entry + execution_cost if direction == "Long" else raw_entry - execution_cost

            # Phase 15: Dynamic Kelly Sizing
            balance = broker.get_account_balance()
            lot_size = calculate_kelly_position_size(
                ticker=ticker, entry=final_entry, stop_loss=signal['sl_price'],
                balance=balance, win_rate=win_rate, avg_win=avg_win, avg_loss=avg_loss
            )

            if lot_size <= 0: continue

            # Execute
            receipt = broker.place_market_order(
                ticker=ticker, direction=direction, size=lot_size,
                sl=signal['sl_price'], tp=signal['tp_price'], current_price=final_entry
            )

            await send_telegram_message(
                f"🚨 YÜKSEK GÜVENİLİRLİKLİ SİNYAL UYGULANDI (MTF/ML/NLP) 🚨\n\n"
                f"Varlık: {ticker}\n"
                f"Yön: {direction}\n"
                f"Giriş: {receipt['executed_price']:.4f}\n"
                f"SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}\n"
                f"Lot: {receipt['size']:.4f}\n"
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
        pnl = (current_price - pos['entry_price']) * pos['position_size'] if pos['direction'] == 'Long' else (pos['entry_price'] - current_price) * pos['position_size']
        pct = (pnl / pos['entry_price']) * 100
        broker.close_position(str(pos['trade_id']), current_price, pnl, pct)
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
    schedule.every(5).minutes.do(run_async_task, check_open_positions_task)
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
