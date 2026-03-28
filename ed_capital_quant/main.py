import schedule
import time
import asyncio
from data.data_loader import get_mtf_data
from features.indicators import add_features
from strategy.signals import generate_signals, calc_dynamic_sl_tp
from core.ml_validator import validate_signal
from execution.execution_model import apply_slippage_and_spread
from execution.broker import broker
from core.paper_db import db
from core.config import UNIVERSE, INITIAL_CAPITAL, MAX_OPEN_POSITIONS, MAX_GLOBAL_EXPOSURE, MAX_CORRELATION
from execution.portfolio import calculate_position_size, calculate_correlation, is_correlated
from utils.notifier import send_msg, start_polling
from utils.logger import log

# Global state control for Telegram Admin Commands
STATE = {"paused": False}

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

        # DYNAMIC TRAILING STOP (Phase 12) & BREAKEVEN
        # Calculate Breakeven: if price moved 1x SL distance in our favor
        risk_dist = abs(entry - sl)
        if direction == 1:
            if current_price >= entry + risk_dist and sl < entry:
                db.update_sl(trade_id, entry)
                await send_msg(f"🔒 Risk Sıfırlandı: {ticker} SL giriş fiyatına çekildi.")

            # Trailing Stop: Price moved further up, trail SL behind
            new_sl = current_price - (1.5 * risk_dist)
            if new_sl > sl and new_sl > entry:
                db.update_sl(trade_id, new_sl)

        else: # Short
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
            # Re-apply slippage on exit
            exit_price = apply_slippage_and_spread(ticker, current_price, risk_dist/1.5, direction=-direction)
            if direction == 1: pnl = (exit_price - entry) * size
            else: pnl = (entry - exit_price) * size

            db.close_trade(trade_id, exit_price, pnl)
            await send_msg(f"🔒 İşlem Kapandı: {ticker} | PnL: ${pnl:.2f}")

async def run_cycle():
    if STATE["paused"]:
        log.info("Sistem duraklatılmış durumda. Tarama yapılmıyor.")
        return

    log.info("ED Capital Engine: Döngü Başladı")
    await send_msg("🔍 ED Capital: Tarama Başlatıldı")

    flat_tickers = [t for group in UNIVERSE.values() for t in group]
    current_prices = {}

    # Portfolio Limits (Phase 11)
    open_trades = db.get_open_trades()
    open_tickers = open_trades['ticker'].tolist() if not open_trades.empty else []

    if len(open_tickers) >= MAX_OPEN_POSITIONS:
        log.warning("Maksimum açık pozisyon sınırına ulaşıldı. Yeni sinyal aranmıyor.")
        await check_open_positions(current_prices) # Sadece açıkları kontrol et
        return

    # Correlation Matrix
    corr_matrix = calculate_correlation(flat_tickers)

    for ticker in flat_tickers:
        try:
            df = get_mtf_data(ticker)
            if df.empty: continue
            current_prices[ticker] = df['Close'].iloc[-1]
            df = add_features(df)

            signal = generate_signals(df, ticker)
            if signal != 0:
                # Phase 18: ML Veto
                if not validate_signal(df):
                    log.info(f"ML Vetosu: {ticker} düşük ihtimalli sinyal reddedildi.")
                    continue

                # Phase 11: Correlation Veto
                if is_correlated(ticker, open_tickers, corr_matrix, MAX_CORRELATION):
                    log.info(f"Korelasyon Vetosu: {ticker} risk duplikasyonu sebebiyle reddedildi.")
                    continue

                entry_raw = df['Close'].iloc[-1]
                atr = df['ATRr_14'].iloc[-1] if 'ATRr_14' in df.columns else df['ATR_14'].iloc[-1]

                # Phase 21 & 24: Real Execution Cost Simulation
                entry_real = apply_slippage_and_spread(ticker, entry_raw, atr, signal)
                sl, tp = calc_dynamic_sl_tp(entry_real, atr, signal)

                # Phase 15: Kelly Sizing
                size = calculate_position_size(INITIAL_CAPITAL, entry_real, sl)

                # Phase 24: Broker Abstraction Layer
                broker.place_market_order(ticker, signal, entry_real, sl, tp, size)

                dir_str = "LONG" if signal == 1 else "SHORT"
                msg = f"🟢 SİNYAL ONAYLANDI: {ticker} {dir_str}\nGerçekçi Giriş: {entry_real:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}\nBoyut: {size:.2f}"
                await send_msg(msg)
                log.info(f"Sinyal İşleme Alındı: {ticker} {dir_str}")

        except Exception as e:
            log.error(f"Döngü Hatası ({ticker}): {e}")

    await check_open_positions(current_prices)

def job():
    asyncio.run(run_cycle())

async def background_scheduler():
    schedule.every().hour.at(":01").do(job)
    log.info("Sistem Başlatıldı. Zamanlayıcı ve Telegram aktif.")
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    # Gather polling and scheduler so both run simultaneously
    await asyncio.gather(
        start_polling(),
        background_scheduler()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Sistem durduruldu.")
