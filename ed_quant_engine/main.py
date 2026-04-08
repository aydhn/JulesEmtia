import asyncio
import schedule
import time
from datetime import datetime
import gc
import pandas as pd
import yfinance as yf

from src.logger import get_logger
from src.config import ALL_TICKERS, get_spread
from src.data_loader import get_mtf_data, fetch_macro_data
from src.features import merge_mtf_data
from src.macro_filter import check_circuit_breaker, check_flash_crash, check_macro_regime_veto
from src.sentiment_filter import fetch_rss_sentiment
from src.portfolio import check_global_limits, calculate_correlation_matrix, check_correlation_veto
from src.strategy import generate_signals, manage_open_positions
from src.broker import PaperBroker
from src.notifier import get_telegram_application, send_telegram_message, send_telegram_document
from src.ml_validator import validate_signal, train_model
from src.reporter import create_tear_sheet
import src.paper_db as db

logger = get_logger()
broker = PaperBroker()

async def panic_close_all():
    """Immediately closes all open positions."""
    logger.warning("Panic Close All Triggered.")
    open_trades = broker.get_open_positions()

    if not open_trades:
        await send_telegram_message("Açık pozisyon bulunamadı.")
        return

    for trade in open_trades:
        ticker = trade['ticker']
        try:
            current_data = await asyncio.to_thread(yf.download, tickers=ticker, period="1d", interval="1m", progress=False)
            if current_data.empty:
                continue

            if isinstance(current_data.columns, pd.MultiIndex):
                current_price = current_data['Close'][ticker].iloc[-1]
            else:
                current_price = current_data['Close'].iloc[-1]

            broker.close_position(trade['trade_id'], current_price)
        except Exception as e:
            logger.error(f"Error panic closing {ticker}: {e}")

    await send_telegram_message("✅ Panik kapatması tamamlandı.")

async def run_live_cycle():
    from src.notifier import engine_paused

    logger.info("Starting live cycle...")

    # 1. Fetch Macro Data & Check Circuit Breakers
    macro_data = fetch_macro_data()
    black_swan = check_circuit_breaker(macro_data)

    if black_swan:
        await send_telegram_message(f"🚨 <b>VIX DEVRE KESİCİ AKTİF!</b> (VIX: {macro_data.get('VIX', 0):.2f}) Yeni işlemler durduruldu.")

    # 2. Fetch MTF Data for Universe
    df_dict = {}
    price_dict = {}
    for ticker in ALL_TICKERS:
        try:
            mtf_raw = await get_mtf_data(ticker)
            if mtf_raw['ltf'].empty or mtf_raw['htf'].empty:
                continue

            merged_df = merge_mtf_data(mtf_raw['ltf'], mtf_raw['htf'])

            # Z-Score Flash Crash Check
            if check_flash_crash(merged_df):
                logger.warning(f"{ticker} halted due to Z-Score Flash Crash anomaly.")
                continue

            df_dict[ticker] = merged_df
            price_dict[ticker] = merged_df['Close']
        except Exception as e:
            logger.error(f"Error processing {ticker}: {e}")

    # 3. Manage Open Positions (Always runs, even in Black Swan or Paused)
    manage_open_positions(broker, df_dict, black_swan)

    # Check if we should search for new signals
    if black_swan or engine_paused:
        logger.info("Skipping new signal generation due to Black Swan or Pause.")
        return

    # 4. Filters & Correlation
    corr_matrix = calculate_correlation_matrix(price_dict)
    current_balance = broker.get_account_balance()

    if not check_global_limits(current_balance):
        return

    sentiment_score = await fetch_rss_sentiment()

    # 5. Signal Generation & Validation
    for ticker, df in df_dict.items():
        signal = generate_signals(df, ticker, current_balance, macro_data.get("Regime", "Risk-On"))
        if signal:
            # Macro Regime Veto
            if not check_macro_regime_veto(ticker, signal['direction'], macro_data):
                continue

            # ML Validation
            if not validate_signal(signal['features']):
                continue

            # Correlation Veto
            if not check_correlation_veto(ticker, signal['direction'], corr_matrix):
                continue

            # Sentiment Veto
            if signal['direction'] == 'Long' and sentiment_score < -0.3:
                logger.info(f"Sentiment Veto: Rejected Long on {ticker} due to negative news.")
                continue
            elif signal['direction'] == 'Short' and sentiment_score > 0.3:
                logger.info(f"Sentiment Veto: Rejected Short on {ticker} due to positive news.")
                continue

            # 6. Execution
            receipt = broker.place_market_order(
                ticker=signal['ticker'],
                direction=signal['direction'],
                market_price=signal['entry_price'],
                sl_price=signal['sl_price'],
                tp_price=signal['tp_price'],
                position_size=signal['position_size'],
                atr=signal['features'].get('ATR_14', 0.0)
            )

            msg = f"🟢 <b>YENİ İŞLEM AÇILDI</b>\n" \
                  f"Varlık: {ticker}\nYön: {signal['direction']}\n" \
                  f"Giriş: {receipt['execution_price']:.4f}\n" \
                  f"SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}\n" \
                  f"Miktar: {signal['position_size']:.4f}"
            await send_telegram_message(msg)

            # Recheck limits after opening a trade
            if not check_global_limits(broker.get_account_balance()):
                break

    # 7. Garbage Collection
    del df_dict
    del price_dict
    gc.collect()
    logger.info("Live cycle completed.")

def scheduled_job():
    # Wrap async execution for schedule library
    asyncio.create_task(run_live_cycle())

async def daily_heartbeat():
    open_trades = len(broker.get_open_positions())
    msg = f"🟢 <b>Sistem Aktif (Heartbeat)</b>\n" \
          f"Kasa: ${broker.get_account_balance():.2f}\n" \
          f"Açık Pozisyonlar: {open_trades}"
    await send_telegram_message(msg)

def heartbeat_job():
    asyncio.create_task(daily_heartbeat())

async def weekly_report():
    report_path = create_tear_sheet()
    if report_path:
        await send_telegram_document(report_path)

def report_job():
    asyncio.create_task(weekly_report())

async def retrain_model_async():
    logger.info("Starting weekend ML model retraining...")
    # Gather historical data for a few diverse tickers
    df_list = []
    for ticker in ["GC=F", "CL=F", "EURTRY=X"]:
        try:
            df = await asyncio.to_thread(yf.download, tickers=ticker, period="5y", interval="1d", progress=False)
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                from src.features import add_features
                df = add_features(df, "1d")
                df_list.append(df)
        except Exception as e:
            logger.error(f"Error fetching training data for {ticker}: {e}")

    if df_list:
        combined_df = pd.concat(df_list, ignore_index=True)
        train_model(combined_df)
    logger.info("Weekend ML model retraining complete.")

def retrain_job():
    asyncio.create_task(retrain_model_async())

async def main():
    logger.info("Initializing ED Capital Quant Engine...")
    db.init_db()

    # Start Telegram Bot
    telegram_app = get_telegram_application()
    if telegram_app:
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        logger.info("Telegram bot started.")
        await send_telegram_message("🚀 <b>ED Capital Quant Engine Başlatıldı.</b>")

    # Schedule Jobs
    # Using minute 1 to ensure candle is fully closed at hour mark
    schedule.every().hour.at(":01").do(scheduled_job)
    schedule.every().day.at("08:00").do(heartbeat_job)
    schedule.every().friday.at("23:00").do(report_job)
    schedule.every().saturday.at("10:00").do(retrain_job)

    logger.info("Scheduler running. Entering main loop.")

    # Main Loop
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.critical(f"Bot crashed: {e}")
