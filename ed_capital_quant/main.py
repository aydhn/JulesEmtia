import schedule
import time
import asyncio
import gc
from data.data_loader import get_mtf_data
from features.indicators import add_features
from strategy.signals import generate_signals, calc_dynamic_sl_tp
from core.ml_validator import validate_signal
from execution.execution_model import apply_slippage_and_spread
from execution.broker import broker
from core.paper_db import db
from core.config import UNIVERSE, INITIAL_CAPITAL, MAX_OPEN_POSITIONS, MAX_GLOBAL_EXPOSURE, MAX_CORRELATION
from execution.portfolio import calculate_position_size, calculate_correlation, is_correlated
from utils.notifier import send_msg, start_polling, STATE
from utils.logger import log
from data.macro_filter import check_vix_circuit_breaker
from analytics.reporter import generate_tear_sheet
from core.ml_validator import train_model

async def panic_close_all():
    open_trades = db.get_open_trades()
    if open_trades.empty:
        await send_msg("Kapatılacak açık işlem yok.")
        return

    for _, trade in open_trades.iterrows():
        trade_id = trade['trade_id']
        ticker = trade['ticker']
        dir_val = trade['direction']
        size = trade['position_size']
        entry = trade['entry_price']

        df = get_mtf_data(ticker)
        if df.empty: continue
        current_price = df['Close'].iloc[-1]

        # SL/TP calculation mock for slippage
        risk_dist = abs(entry - trade['sl_price'])
        exit_price = apply_slippage_and_spread(ticker, current_price, risk_dist/1.5 if risk_dist > 0 else 0, direction=-dir_val)

        if dir_val == 1: pnl = (exit_price - entry) * size
        else: pnl = (entry - exit_price) * size

        db.close_trade(trade_id, exit_price, pnl)

    await send_msg("🚨 PANİK MODU: Tüm İşlemler Kapatıldı.")
    STATE["panic_close"] = False

async def check_open_positions(current_prices: dict):
    open_trades = db.get_open_trades()
    for _, trade in open_trades.iterrows():
        ticker = trade['ticker']
        if ticker not in current_prices: continue

        current_price = current_prices[ticker]
        direction = trade['direction']
        sl = trade['sl_price']
        tp = trade['tp_price']
        entry = trade['entry_price']
        size = trade['position_size']
        trade_id = trade['trade_id']

        # Risk_dist equivalent to 1.5 ATR (from calc_dynamic_sl_tp)
        risk_dist = abs(entry - sl)

        # Phase 12: Breakeven & Trailing Stop strictly monotonic
        if direction == 1:
            # Breakeven: if price moved 1x SL distance in our favor
            if current_price >= entry + risk_dist and sl < entry:
                db.update_sl(trade_id, entry)
                await send_msg(f"🔒 Risk Sıfırlandı: {ticker} SL giriş fiyatına çekildi.")

            # Trailing Stop: Move SL up if price made new high
            new_sl = current_price - (1.5 * risk_dist)
            if new_sl > sl and new_sl > entry:
                db.update_sl(trade_id, new_sl)

        else: # Short
            # Breakeven
            if current_price <= entry - risk_dist and sl > entry:
                db.update_sl(trade_id, entry)
                await send_msg(f"🔒 Risk Sıfırlandı: {ticker} SL giriş fiyatına çekildi.")

            # Trailing Stop
            new_sl = current_price + (1.5 * risk_dist)
            if new_sl < sl and new_sl < entry:
                db.update_sl(trade_id, new_sl)

        # EXIT LOGIC
        closed = False
        pnl = 0.0

        if direction == 1:
            if current_price <= sl:
                closed = True
                pnl = (sl - entry) * size
            elif current_price >= tp:
                closed = True
                pnl = (tp - entry) * size
        else:
            if current_price >= sl:
                closed = True
                pnl = (entry - sl) * size
            elif current_price <= tp:
                closed = True
                pnl = (entry - tp) * size

        if closed:
            exit_price = apply_slippage_and_spread(ticker, current_price, risk_dist/1.5, direction=-direction)
            if direction == 1: pnl = (exit_price - entry) * size
            else: pnl = (entry - exit_price) * size

            db.close_trade(trade_id, exit_price, pnl)
            await send_msg(f"🔒 İşlem Kapandı: {ticker} | PnL: ${pnl:.2f}")

async def run_cycle():
    if STATE["panic_close"]:
        await panic_close_all()

    if STATE["paused"]:
        log.info("Sistem duraklatılmış durumda. Sadece açık pozisyonlar güncellenecek.")

    flat_tickers = [t for group in UNIVERSE.values() for t in group]
    current_prices = {}

    log.info("ED Capital Engine: Döngü Başladı")

    open_trades = db.get_open_trades()
    open_tickers = open_trades['ticker'].tolist() if not open_trades.empty else []

    # Phase 19: VIX Circuit Breaker blocks NEW trades, but open trades continue to be checked
    vix_breaker_active = check_vix_circuit_breaker()

    # Pre-fetch prices to check stops
    for ticker in flat_tickers:
        try:
            df = get_mtf_data(ticker)
            if not df.empty:
                current_prices[ticker] = df['Close'].iloc[-1]
        except Exception as e:
            log.error(f"Fiyat çekme hatası ({ticker}): {e}")

    await check_open_positions(current_prices)

    if STATE["paused"] or vix_breaker_active:
        return # Skip new trade scanning

    if len(open_tickers) >= MAX_OPEN_POSITIONS:
        log.warning("Maksimum açık pozisyon sınırına ulaşıldı.")
        return

    # Phase 11: Correlation
    corr_matrix = calculate_correlation(flat_tickers)

    for ticker in flat_tickers:
        try:
            df = get_mtf_data(ticker)
            if df.empty: continue

            df = add_features(df)
            signal = generate_signals(df, ticker)

            if signal != 0:
                # Phase 18: Machine Learning Validation
                if not validate_signal(df):
                    log.info(f"ML Vetosu: {ticker} modeli geçemedi.")
                    continue

                # Phase 11: Correlation Check
                if is_correlated(ticker, open_tickers, corr_matrix, MAX_CORRELATION):
                    log.info(f"Korelasyon Vetosu: {ticker} risk duplikasyonu.")
                    continue

                entry_raw = df['Close'].iloc[-1]
                atr = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else df['ATR_14'].iloc[-1]

                # Phase 21: Spread and Slippage Modeling
                entry_real = apply_slippage_and_spread(ticker, entry_raw, atr, signal)
                sl, tp = calc_dynamic_sl_tp(entry_real, atr, signal)

                # Phase 15: Half-Kelly Sizing
                size = calculate_position_size(INITIAL_CAPITAL, entry_real, sl)

                if size > 0:
                    broker.place_market_order(ticker, signal, entry_real, sl, tp, size)

                    dir_str = "LONG" if signal == 1 else "SHORT"
                    msg = f"🟢 SİNYAL ONAYLANDI: {ticker} {dir_str}\nGiriş: {entry_real:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nBoyut: {size:.2f}"
                    await send_msg(msg)
                    log.info(f"Sinyal İşleme Alındı: {ticker} {dir_str}")

        except Exception as e:
            log.error(f"Döngü Hatası ({ticker}): {e}")

    STATE["force_scan"] = False

    # Phase 23: Memory Management (Garbage Collection)
    gc.collect()

def generate_weekly_report():
    file_path = generate_tear_sheet()
    log.info("Haftalık Rapor Oluşturuldu: " + file_path)

def retrain_ml_model():
    log.info("Haftasonu ML Model Eğitimi Başlıyor...")
    # Gather massive historical dataframe across universe and retrain
    # In real deployment, iterate through UNIVERSE and concat dfs
    # train_model(massive_df)

def job():
    asyncio.run(run_cycle())

async def background_scheduler():
    schedule.every().hour.at(":01").do(job)

    # Run tear sheet and retraining on Friday night / Saturday
    schedule.every().friday.at("23:00").do(generate_weekly_report)
    schedule.every().saturday.at("02:00").do(retrain_ml_model)

    log.info("Sistem Başlatıldı. Zamanlayıcı ve Telegram aktif.")
    await send_msg("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")

    # Attempt initial recovery state logic
    open_trades = db.get_open_trades()
    log.info(f"State Recovery: {len(open_trades)} adet açık pozisyon bulundu ve izleniyor.")

    while True:
        schedule.run_pending()

        # Admin Forced Scan
        if STATE["force_scan"]:
            await run_cycle()
            STATE["force_scan"] = False

        await asyncio.sleep(1)

async def main():
    await asyncio.gather(
        start_polling(),
        background_scheduler()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Sistem durduruldu.")
