import asyncio
import gc
import os
import schedule
import pandas as pd
from core.paper_db import PaperDB
from core.notifier import TelegramNotifier
from data.data_loader import DataLoader
from data.macro_filter import MacroRegime
from data.sentiment_filter import SentimentFilter
from quant.features import add_features
from quant.strategy import StrategyEngine
from quant.portfolio_mgr import PortfolioManager
from quant.ml_validator import MLValidator
from execution.broker import PaperBroker
from core.config import TICKERS
from core.logger import logger
from quant.reporter import Reporter
from quant.monte_carlo import MonteCarloSimulator
import datetime

db = PaperDB()
notifier = TelegramNotifier(db)
broker = PaperBroker(db)
portfolio = PortfolioManager(db)
ml_engine = MLValidator()
sentiment_engine = SentimentFilter()
reporter = Reporter(db)

async def manage_open_trades():
    open_trades = db.get_open_trades()
    for _, trade in open_trades.iterrows():
        df = DataLoader.fetch_data(trade['ticker'], "1h", "5d", retries=1)
        if df.empty: continue

        try:
            current_price = df['Close'].iloc[-1].item() if not isinstance(df.columns, pd.MultiIndex) else df['Close'].iloc[-1, 0].item()

            import pandas_ta as ta
            df_ta = df.copy()
            if isinstance(df_ta.columns, pd.MultiIndex):
                df_ta.columns = [c[0] for c in df_ta.columns]
            atr = df_ta.ta.atr(length=14).iloc[-1].item()
        except Exception as e:
            logger.error(f"Error managing trade {trade['ticker']}: {e}")
            continue

        if MacroRegime.check_black_swan() or MacroRegime.is_flash_crash(df):
            pnl = (current_price - trade['entry_price']) if trade['direction'] == "Long" else (trade['entry_price'] - current_price)
            db.close_trade(trade['trade_id'], current_price, datetime.datetime.now().isoformat(), pnl)
            await notifier.send_message(f"🚨 <b>DEVRE KESİCİ ÇIKIŞI</b>\n{trade['ticker']} kapatıldı. PNL: {pnl:.2f}")
            continue

        hit_sl = (trade['direction'] == "Long" and current_price <= trade['sl_price']) or \
                 (trade['direction'] == "Short" and current_price >= trade['sl_price'])
        hit_tp = (trade['direction'] == "Long" and current_price >= trade['tp_price']) or \
                 (trade['direction'] == "Short" and current_price <= trade['tp_price'])

        if hit_sl or hit_tp:
            pnl = (current_price - trade['entry_price']) * trade['position_size'] if trade['direction'] == "Long" else (trade['entry_price'] - current_price) * trade['position_size']
            db.close_trade(trade['trade_id'], current_price, datetime.datetime.now().isoformat(), pnl)
            await notifier.send_message(f"✅ <b>İŞLEM KAPANDI</b>\n{trade['ticker']} PNL: {pnl:.2f}")
        else:
            new_sl = StrategyEngine.manage_trailing_stop(trade, current_price, atr)
            if new_sl != trade['sl_price']:
                db.update_sl(trade['trade_id'], new_sl)
                if new_sl == trade['entry_price']:
                    await notifier.send_message(f"🔒 <b>RİSK SIFIRLANDI</b>\n{trade['ticker']} SL Başa Başa Çekildi.")

def _run_live_cycle_sync():
    """Wrapper to run the async cycle from the synchronous scheduler"""
    asyncio.create_task(run_live_cycle())

def _generate_weekly_report():
    """Wrapper to generate weekly report via async notifier"""
    asyncio.create_task(send_weekly_report())

async def send_weekly_report():
    report_path = reporter.generate_tear_sheet()
    await notifier.send_message(f"📊 <b>Haftalık ED Capital Raporu Oluşturuldu!</b>\nKonumu: {report_path}")

async def panic_close_all():
    open_trades = db.get_open_trades()
    for _, trade in open_trades.iterrows():
        df = DataLoader.fetch_data(trade['ticker'], "1h", "1d", retries=1)
        if df.empty: continue
        current_price = df['Close'].iloc[-1].item() if not isinstance(df.columns, pd.MultiIndex) else df['Close'].iloc[-1, 0].item()
        pnl = (current_price - trade['entry_price']) * trade['position_size'] if trade['direction'] == "Long" else (trade['entry_price'] - current_price) * trade['position_size']
        db.close_trade(trade['trade_id'], current_price, datetime.datetime.now().isoformat(), pnl)
        await notifier.send_message(f"🚨 <b>PANİK KAPATMASI</b>\n{trade['ticker']} piyasa fiyatından kapatıldı. PNL: {pnl:.2f}")

async def run_live_cycle():
    logger.info("Canlı Döngü Tetiklendi.")
    if notifier.is_paused:
        logger.info("Sistem duraklatılmış durumda (Paused). Sinyal taranmıyor.")
        return

    if MacroRegime.check_black_swan():
        return

    await manage_open_trades()

    if len(db.get_open_trades()) >= 4:
        logger.info("Maksimum pozisyon limitine ulaşıldı.")
        return

    sentiment_score = sentiment_engine.get_market_sentiment()
    current_capital = 10000.0 # Could fetch from DB

    # Calculate historical stats for Kelly Criterion
    closed_trades = pd.read_sql("SELECT * FROM trades WHERE status='Closed' ORDER BY exit_time DESC LIMIT 50", db.conn)
    win_rate, avg_win, avg_loss = 0.5, 0.0, 0.0
    if not closed_trades.empty:
        wins = closed_trades[closed_trades['pnl'] > 0]
        losses = closed_trades[closed_trades['pnl'] < 0]
        win_rate = len(wins) / len(closed_trades)
        avg_win = wins['pnl'].mean() if not wins.empty else 0
        avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 0

    kelly_pct = portfolio.kelly_criterion(win_rate, avg_win, avg_loss)
    # Fallback to minimal fixed risk if no history or negative Kelly
    if kelly_pct <= 0:
        kelly_pct = 0.005

    for category, ticker_list in TICKERS.items():
        for ticker in ticker_list:
            # Recheck limits inside loop
            if len(db.get_open_trades()) >= 4: break

            df = DataLoader.get_mtf_data(ticker)
            if df is None or df.empty: continue

            df = add_features(df)
            signal = StrategyEngine.check_signal(df)

            if signal:
                # 1. Macro Regime Filter (e.g. Risk-Off DXY/TNX vetoes Longs)
                if MacroRegime.veto_signal(signal, ticker):
                    continue

                # 2. Sentiment Veto
                if (signal == "Long" and sentiment_score < -0.2) or (signal == "Short" and sentiment_score > 0.2):
                    logger.info(f"Sentiment Vetosu: {ticker} {signal} reddedildi.")
                    continue

                # 3. Correlation Veto
                # For simplicity in live cycle, passing the universe df representing just this asset.
                # In real scenario, a global universe df is needed.
                if portfolio.correlation_veto(ticker, signal, df):
                    logger.info(f"Korelasyon Vetosu: {ticker} {signal} reddedildi.")
                    continue

                # 4. ML Validation Veto
                import numpy as np
                # Extract last features for ML
                try:
                    features = df[['RSI_14', 'MACD_12_26_9', 'ATRr_14', 'log_ret']].iloc[-1].fillna(0).values
                    if not ml_engine.validate_signal(features):
                        continue
                except Exception as e:
                    logger.warning(f"ML extraction failed for {ticker}: {e}")

                try:
                    last_price = df['Close'].iloc[-1].item() if 'Close' in df.columns else df.iloc[-1, 0].item()
                    atr = df['ATRr_14'].iloc[-1].item()
                except:
                    continue

                sl, tp = StrategyEngine.calculate_dynamic_risk(last_price, atr, signal)

                # Use Kelly Criterion
                risk_amount = current_capital * kelly_pct
                lot_size = risk_amount / abs(last_price - sl) if abs(last_price - sl) > 0 else 0

                if lot_size > 0:
                    receipt = broker.place_order(ticker, signal, last_price, atr, category, lot_size, sl, tp)
                    await notifier.send_message(f"🟢 <b>YENİ SİNYAL ONAYLANDI</b>\nTicker: {ticker}\nYön: {signal}\nFiyat: {receipt['entry_price']:.2f}\nSL: {sl:.2f}\nTP: {tp:.2f}\nLot: {lot_size:.2f}\nKelly Pct: {kelly_pct:.4f}")

    gc.collect()
    logger.info("Canlı Döngü Tamamlandı.")

def setup_schedule():
    schedule.every().hour.at(":00").do(_run_live_cycle_sync)
    schedule.every().day.at("08:00").do(
        lambda: asyncio.create_task(notifier.send_message("🟢 <b>Sistem Aktif</b>: Bot 7/24 çalışıyor."))
    )
    # Generate weekly report on Friday close (e.g., 23:00)
    schedule.every().friday.at("23:00").do(_generate_weekly_report)
    logger.info("Zamanlayıcı (Scheduler) ayarlandı.")

async def main_loop():
    # Pass cycle funcs to notifier if it needs to call them
    notifier.run_live_cycle = run_live_cycle
    notifier.panic_close_all = panic_close_all

    if notifier.app:
        await notifier.app.initialize()
        await notifier.app.start()
        await notifier.app.updater.start_polling()

    await notifier.send_message("🚀 <b>ED Capital Quant Engine</b> Canlı Paper Trade Modunda Başlatıldı.")

    setup_schedule()

    await run_live_cycle()

    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot durduruldu.")
