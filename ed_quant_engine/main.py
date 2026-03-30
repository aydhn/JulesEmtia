import asyncio
import schedule
from datetime import datetime
import gc
from logger import logger
import config
from universe import TICKERS
from data_loader import fetch_mtf_data
from features import add_features
from macro_filter import macro_filter
from sentiment_filter import sentiment_filter
from ml_validator import ml_validator
from portfolio_manager import portfolio_manager
from strategy import generate_signals
from paper_broker import PaperBroker

from notifier import notifier

broker = PaperBroker()

async def manage_open_positions():
    ''' Phase 12: Trailing Stop & Breakeven logic '''
    positions = await broker.get_open_positions()
    if not positions: return

    logger.info(f"Managing {len(positions)} open positions...")

    for pos in positions:
        trade_id = pos['trade_id']
        ticker = pos['ticker']
        direction = pos['direction']
        entry_price = pos['entry_price']
        sl_price = pos['sl_price']
        tp_price = pos['tp_price']

        import data_loader
        df_1m = await data_loader.fetch_data_with_retry(ticker, "1d", "1m", retries=2)
        if df_1m.empty: continue

        current_price = df_1m['Close'].iloc[-1].item()

        from execution_model import get_execution_price
        current_atr = current_price * 0.005
        avg_atr = current_atr

        exit_price = get_execution_price(ticker, current_price, "Short" if direction=="Long" else "Long", current_atr, avg_atr)

        hit_tp = False
        hit_sl = False

        if direction == "Long":
            if current_price >= tp_price: hit_tp = True
            elif current_price <= sl_price: hit_sl = True
        else:
            if current_price <= tp_price: hit_tp = True
            elif current_price >= sl_price: hit_sl = True

        if hit_tp or hit_sl:
            pnl = await broker.close_position(trade_id, exit_price)
            reason = "Kâr Al (TP)" if hit_tp else "Zarar Kes (SL)"
            logger.info(f"Position Closed: {direction} {ticker} @ {exit_price:.4f} ({reason}) PnL: ${pnl:.2f}")
            await notifier.send_message(f"🔔 İşlem Kapandı: {direction} {ticker}Neden: {reason}Çıkış: {exit_price:.4f}PnL: ${pnl:.2f}")
            continue

        dist_moved = (current_price - entry_price) if direction == "Long" else (entry_price - current_price)

        if dist_moved > current_atr:
             if direction == "Long" and sl_price < entry_price:
                 await broker.modify_trailing_stop(trade_id, entry_price)
                 await notifier.send_message(f"🔒 Risk Sıfırlandı: {ticker} SL seviyesi giriş fiyatına çekildi (Breakeven).")
             elif direction == "Short" and sl_price > entry_price:
                 await broker.modify_trailing_stop(trade_id, entry_price)
                 await notifier.send_message(f"🔒 Risk Sıfırlandı: {ticker} SL seviyesi giriş fiyatına çekildi (Breakeven).")

        # Trailing stop update logic
        if direction == "Long" and current_price > (sl_price + 1.5 * current_atr):
            new_sl = current_price - (1.5 * current_atr)
            if new_sl > sl_price:
                await broker.modify_trailing_stop(trade_id, new_sl)
        elif direction == "Short" and current_price < (sl_price - 1.5 * current_atr):
            new_sl = current_price + (1.5 * current_atr)
            if new_sl < sl_price:
                 await broker.modify_trailing_stop(trade_id, new_sl)

async def run_live_cycle():
    ''' Phase 23: Asynchronous Pipeline Orchestration '''
    logger.info("=== Starting Live MTF Cycle ===")

    await macro_filter.fetch_macro_data()
    await sentiment_filter.fetch_news()

    await manage_open_positions()

    if await macro_filter.check_vix_circuit_breaker():
         if not notifier.is_paused:
             await notifier.send_message("🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi! Yeni İşlemler Durduruldu.")
             notifier.is_paused = True
         return

    open_positions = await broker.get_open_positions()
    if not portfolio_manager.check_global_limits(open_positions):
         logger.info("Global Exposure Limit reached. Skipping new signals.")
         return

    if notifier.is_paused:
         logger.info("Scanner paused by admin.")
         return

    import yfinance as yf
    import pandas as pd
    flat_tickers = [t for v in TICKERS.values() for t in v]
    returns_df = await portfolio_manager.fetch_daily_returns_matrix(flat_tickers)
    corr_matrix = portfolio_manager.calculate_correlation_matrix(returns_df)

    current_balance = await broker.get_account_balance()
    from paper_db import paper_db
    recent_trades = paper_db.get_recent_trades(limit=50)

    for category, tickers in TICKERS.items():
        for ticker in tickers:
            df = await fetch_mtf_data(ticker)
            if df.empty: continue

            if macro_filter.check_zscore_anomaly(df):
                logger.warning(f"Z-Score anomaly detected on {ticker}. Skipping.")
                continue

            df_feat = add_features(df)

            signal = generate_signals(df_feat, ticker, current_balance, open_positions, corr_matrix, recent_trades)

            if signal:
                await broker.place_order(
                    signal['ticker'], signal['direction'], signal['size'],
                    signal['entry_price'], signal['sl_price'], signal['tp_price']
                )

                msg = f"🟢 YENI ISLEM AÇILDI: {signal['direction']} {signal['ticker']}"                       f"Giriş: {signal['entry_price']:.4f}"                       f"SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}"                       f"Miktar: {signal['size']:.4f}"
                await notifier.send_message(msg)

    gc.collect()
    logger.info("=== Live Cycle Complete ===")

async def daily_heartbeat():
    from paper_db import paper_db
    open_pos = len(paper_db.get_open_trades())
    bal = await broker.get_account_balance()
    await notifier.send_message(f"🌅 Günlük Durum RaporuSistem Aktif.Açık Pozisyon: {open_pos}Güncel Bakiye: ${bal:.2f}")

async def main():
    # Initial ML Training
    asyncio.create_task(train_ml_model())

    # Scheduled ML Training (Weekly on Saturday)
    schedule.every().saturday.at("02:00").do(lambda: asyncio.create_task(train_ml_model()))
    await notifier.start()
    await notifier.send_message("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")

    await run_live_cycle()

    schedule.every().hour.at(":01").do(lambda: asyncio.create_task(run_live_cycle()))
    schedule.every().day.at("08:00").do(lambda: asyncio.create_task(daily_heartbeat()))

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        logger.info("Starting Quant Engine...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down manually.")
    except Exception as e:
        logger.critical(f"Fatal System Crash: {e}", exc_info=True)
async def train_ml_model():
    logger.info("Starting scheduled ML Model Training...")
    try:
        from data_loader import fetch_mtf_data
        from features import add_features
        from ml_validator import ml_validator

        # Train on a highly liquid asset for general signal validation
        df = await fetch_mtf_data("GC=F")
        if not df.empty:
            df_feat = add_features(df)
            # Run model fitting in thread to avoid blocking
            import asyncio
            await asyncio.to_thread(ml_validator.train, df_feat)
    except Exception as e:
        logger.error(f"Error during ML training: {e}")

# Append to schedule in main loop (will need to manually insert into main() later, so we just add the function here)
