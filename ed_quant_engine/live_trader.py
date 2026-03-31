import asyncio
import schedule
import time
from datetime import datetime
import gc
from typing import Dict, Any

from data_loader import fetch_live_data, fetch_historical_data
from strategy import generate_signals
from paper_broker import PaperBroker
from notifier import send_telegram_message, send_telegram_document
from logger import setup_logger
from macro_filter import get_macro_regime, check_vix_circuit_breaker, check_z_score_anomaly
from portfolio_manager import calculate_correlation_matrix, check_correlation_veto, check_global_exposure, calculate_kelly_position_size
from sentiment_filter import SentimentAnalyzer, check_sentiment_veto
from ml_validator import validate_signal_with_ml, train_and_save_model
from features import add_features

logger = setup_logger("LiveTrader")

# Globals
TICKERS = ["GC=F", "SI=F", "CL=F", "USDTRY=X", "EURTRY=X"]
broker = PaperBroker()
sentiment_analyzer = SentimentAnalyzer()

async def ensure_ml_model():
    """Trains the ML model if it doesn't exist, using historical GC=F data as a proxy."""
    import os
    if not os.path.exists("rf_model.pkl"):
        logger.info("ML Modeli bulunamadı. İlk eğitim başlatılıyor (Geçmiş 2 Yıl Altın Verisi ile)...")
        df = await fetch_historical_data("GC=F", period="2y", interval="1d")
        if not df.empty:
            train_and_save_model(df, "GC=F")
        else:
            logger.error("Veri çekilemedi, ML modeli eğitilemedi.")

async def check_open_positions_task():
    """Monitors open positions for Stop Loss (SL) or Take Profit (TP) hits and dynamically trails SL."""
    logger.info("Açık Pozisyonlar Kontrol Ediliyor...")
    positions = broker.get_open_positions()
    if not positions:
        return

    # Phase 19: Emergency Check
    black_swan = await check_vix_circuit_breaker()
    if black_swan:
        logger.critical("SİYAH KUĞU DEVREDE. Tüm açık pozisyonlar acilen kapatılıyor veya stoplar daraltılıyor!")
        # Implement aggressive exit or trailing stop tightening here

    for pos in positions:
        ticker = pos['ticker']
        trade_id = pos['trade_id']
        direction = pos['direction']
        entry_price = pos['entry_price']
        sl = pos['sl_price']
        tp = pos['tp_price']
        size = pos['position_size']

        df = await fetch_live_data(ticker, interval="1h")
        if df.empty:
            continue

        current_price = df['Close'].iloc[-1]

        # Phase 19: Flash Crash Detection
        if check_z_score_anomaly(df['Close']):
            logger.warning(f"Flaş Çöküş Anomali Tespiti ({ticker}): Pozisyon kapatma işlemi geçici olarak donduruldu veya piyasa emri yasaklandı.")
            continue # Skip normal processing to avoid closing at anomalous wick

        pnl = 0.0
        pnl_percent = 0.0

        if direction == "Long":
            pnl = (current_price - entry_price) * size
            pnl_percent = ((current_price - entry_price) / entry_price) * 100

            # Phase 12: Breakeven & Trailing Stop Logic (Simplified)
            atr = df['High'].iloc[-1] - df['Low'].iloc[-1] # Simple ATR proxy for trailing
            if current_price > entry_price + (1.5 * atr) and sl < entry_price:
                # Breakeven
                broker.modify_trailing_stop(str(trade_id), entry_price)
                await send_telegram_message(f"🔒 Risk Sıfırlandı (Breakeven): {ticker} SL seviyesi giriş fiyatına çekildi.")

            # Trailing stop update if making new highs
            elif current_price > entry_price + (2.0 * atr):
                new_sl = current_price - (1.5 * atr)
                if new_sl > sl: # Strictly monotonic
                    broker.modify_trailing_stop(str(trade_id), new_sl)
                    logger.info(f"Trailing Stop Güncellendi: {ticker} -> {new_sl:.4f}")

            # Exit logic
            if current_price >= tp or current_price <= sl:
                # Simulate exit slippage (Phase 21)
                exit_price = current_price * (1 - 0.0005) # 0.05% slippage on exit
                net_pnl = (exit_price - entry_price) * size
                net_pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                broker.close_position(str(trade_id), exit_price, net_pnl, net_pnl_pct)
                await send_telegram_message(f"🔔 İşlem Kapandı: {direction} {ticker} @ {exit_price:.4f}\nNet Kar/Zarar: {net_pnl:.2f} (%{net_pnl_pct:.2f})")

        elif direction == "Short":
            # Reverse logic for Short
            pnl = (entry_price - current_price) * size
            pnl_percent = ((entry_price - current_price) / entry_price) * 100

            atr = df['High'].iloc[-1] - df['Low'].iloc[-1]
            if current_price < entry_price - (1.5 * atr) and sl > entry_price:
                broker.modify_trailing_stop(str(trade_id), entry_price)
                await send_telegram_message(f"🔒 Risk Sıfırlandı (Breakeven): {ticker} SL seviyesi giriş fiyatına çekildi.")

            elif current_price < entry_price - (2.0 * atr):
                new_sl = current_price + (1.5 * atr)
                if new_sl < sl:
                    broker.modify_trailing_stop(str(trade_id), new_sl)
                    logger.info(f"Trailing Stop Güncellendi: {ticker} -> {new_sl:.4f}")

            if current_price <= tp or current_price >= sl:
                exit_price = current_price * (1 + 0.0005) # 0.05% slippage on exit
                net_pnl = (entry_price - exit_price) * size
                net_pnl_pct = ((entry_price - exit_price) / entry_price) * 100
                broker.close_position(str(trade_id), exit_price, net_pnl, net_pnl_pct)
                await send_telegram_message(f"🔔 İşlem Kapandı: {direction} {ticker} @ {exit_price:.4f}\nNet Kar/Zarar: {net_pnl:.2f} (%{net_pnl_pct:.2f})")

async def run_live_cycle():
    """Main Multi-Timeframe (MTF) Pipeline Orchestrator."""
    logger.info("Canlı Piyasa Döngüsü (MTF) Başladı...")

    # 1. Global Checks
    if await check_vix_circuit_breaker():
        logger.warning("VIX Devre Kesici Aktif. Tarama İptal.")
        return

    if check_global_exposure(max_positions=3):
        return

    macro_regime = await get_macro_regime()
    logger.info(f"Mevcut Makro Rejim: {macro_regime}")

    # Build correlation matrix dict
    prices_dict = {}
    htf_dfs = {}
    ltf_dfs = {}

    # Fetch Data (Phase 16 - MTF)
    for ticker in TICKERS:
        # HTF (1D) for Trend
        htf = await fetch_live_data(ticker, interval="1d")
        # LTF (1H) for Entries
        ltf = await fetch_live_data(ticker, interval="1h")

        if htf.empty or ltf.empty:
            continue

        htf_dfs[ticker] = htf
        ltf_dfs[ticker] = ltf
        prices_dict[ticker] = ltf['Close']

    if not prices_dict:
        return

    corr_matrix = calculate_correlation_matrix(prices_dict)

    for ticker in TICKERS:
        if ticker not in htf_dfs or ticker not in ltf_dfs:
            continue

        htf_df = add_features(htf_dfs[ticker])
        ltf_df = ltf_dfs[ticker]

        if htf_df.empty or ltf_df.empty:
            continue

        # Lookahead Bias Protection: Shift HTF by 1 to ensure we only use *closed* daily candles for hourly signals
        # Reset index to remove timezone if needed, then merge_asof
        htf_shifted = htf_df.shift(1).reset_index()
        ltf_df_reset = ltf_df.reset_index()

        # Ensure both are timezone naive
        if htf_shifted['Date'].dt.tz is not None:
            htf_shifted['Date'] = htf_shifted['Date'].dt.tz_localize(None)
        if ltf_df_reset['Datetime'].dt.tz is not None:
            ltf_df_reset['Datetime'] = ltf_df_reset['Datetime'].dt.tz_localize(None)

        # Merge HTF features onto LTF DataFrame based on time
        merged_df = pd.merge_asof(
            ltf_df_reset.sort_values('Datetime'),
            htf_shifted.sort_values('Date'),
            left_on='Datetime',
            right_on='Date',
            direction='backward',
            suffixes=('', '_HTF')
        )

        # Set index back
        merged_df.set_index('Datetime', inplace=True)

        # Generate Signal on LTF (with HTF Context)
        signal = generate_signals(merged_df, ticker)

        if signal:
            direction = signal['direction']

            # MTF Veto: If Daily EMA50 says DOWN, don't take Hourly LONG
            if 'EMA_50_HTF' in merged_df.columns:
                htf_ema = merged_df['EMA_50_HTF'].iloc[-1]
                htf_close = merged_df['Close_HTF'].iloc[-1]
                if direction == "Long" and htf_close < htf_ema:
                    logger.info(f"MTF Vetosu: Günlük trend AŞAĞI. {ticker} Long sinyali reddedildi.")
                    continue
                if direction == "Short" and htf_close > htf_ema:
                    logger.info(f"MTF Vetosu: Günlük trend YUKARI. {ticker} Short sinyali reddedildi.")
                    continue

            # Correlation Veto (Phase 11)
            if check_correlation_veto(ticker, direction, corr_matrix):
                continue

            # Macro Veto (Phase 6)
            if direction == "Long" and ticker in ["GC=F", "SI=F"] and macro_regime == "Risk-Off":
                logger.warning(f"Makro Veto: Risk-Off rejiminde Değerli Maden (Long) alınamaz. ({ticker})")
                continue

            # ML Validation Veto (Phase 18)
            # Need features for prediction
            ltf_features = add_features(ltf_df) # Recalculate pure LTF features for model
            if not validate_signal_with_ml(ltf_features.iloc[-1]):
                continue

            # Sentiment Veto (Phase 20)
            if check_sentiment_veto(ticker, direction, sentiment_analyzer):
                continue

            # If all checks pass -> Execute!
            balance = broker.get_account_balance()

            # Simulated Kelly (Phase 15)
            # In real system, pull win_rate, avg_win, avg_loss from DB history
            lot_size = calculate_kelly_position_size(
                ticker=ticker,
                entry=signal['entry_price'],
                stop_loss=signal['sl_price'],
                balance=balance,
                win_rate=0.65, # Dummy 65% Win Rate for now
                avg_win=200,
                avg_loss=100
            )

            if lot_size <= 0:
                logger.warning("Kelly hesaplaması 0 lot verdi. İşlem pas geçildi.")
                continue

            # Execute via Broker Layer (Phase 24)
            receipt = broker.place_market_order(
                ticker=ticker,
                direction=direction,
                size=lot_size,
                sl=signal['sl_price'],
                tp=signal['tp_price'],
                current_price=signal['entry_price']
            )

            await send_telegram_message(
                f"🚨 YÜKSEK GÜVENİLİRLİKLİ SİNYAL UYGULANDI (MTF/ML/NLP Onaylı) 🚨\n\n"
                f"Varlık: {ticker}\n"
                f"Yön: {direction}\n"
                f"Uygulanan Fiyat: {receipt['executed_price']:.4f}\n"
                f"SL: {signal['sl_price']:.4f}\n"
                f"TP: {signal['tp_price']:.4f}\n"
                f"Lot: {receipt['size']:.4f}\n"
                f"Bakiye Riski: %{((lot_size*abs(receipt['executed_price']-signal['sl_price']))/balance)*100:.2f}"
            )

    # Memory Management (Phase 23)
    del htf_dfs, ltf_dfs, prices_dict, corr_matrix
    gc.collect()
    logger.info("Döngü tamamlandı, Garbage Collection çalıştırıldı.")

async def send_weekly_report():
    """Generates and sends the weekly tear sheet to Telegram."""
    logger.info("Haftalık Rapor Üretiliyor...")
    from reporter import generate_tear_sheet
    report_path = generate_tear_sheet(initial_balance=float(os.getenv("INITIAL_BALANCE", "10000.0")))
    if report_path:
        await send_telegram_document(report_path, caption="📊 ED Capital Quant Engine - Haftalık Performans Raporu (Tear Sheet)")

def run_async_task(task_func):
    """Wrapper to run async tasks within the synchronous schedule loop without blocking."""
    asyncio.create_task(task_func())

async def live_trading_loop():
    """Main daemon loop."""
    logger.info("LiveTrader Döngüsü Başlatılıyor...")
    await ensure_ml_model()

    balance = broker.get_account_balance()
    await send_telegram_message(f"🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.\nGüncel Portföy: ${balance:,.2f}")

    # Scheduling (Phase 23: Sync with top of the hour)
    schedule.every().hour.at(":01").do(run_async_task, run_live_cycle)
    schedule.every(5).minutes.do(run_async_task, check_open_positions_task)

    # Reporting & Training Maintenance
    schedule.every().friday.at("23:30").do(run_async_task, send_weekly_report)

    # Retrain ML model every Sunday
    def trigger_retrain():
        asyncio.create_task(ensure_ml_model())
    schedule.every().sunday.at("02:00").do(trigger_retrain)

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(live_trading_loop())
    except KeyboardInterrupt:
        logger.warning("Bot manuel olarak durduruldu.")
