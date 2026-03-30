import asyncio
import schedule
import time
import gc
import pandas as pd
from core.config import TICKERS, INITIAL_CAPITAL
from core.data_engine import DataEngine, db
from core.quant_logic import Strategy
from core.execution import PaperBroker
from core.risk_manager import RiskManager
from core.ai_filters import NLPFilter, MLValidator
from system.telegram_bot import tg
from system.logger import log
from core.analysis import Analyzer

broker = PaperBroker()
nlp = NLPFilter()
ml = MLValidator()

async def run_live_cycle():
    """Phase 23: Canlı İleriye Dönük Kesintisiz Boru Hattı"""
    if tg.is_paused:
        log.info("Sistem Duraklatıldı. Sadece AÇIK pozisyonlar takip edilecek.")

    log.info("Canlı Döngü (Candle-Close Synchronization) Başladı.")
    current_prices = {}
    current_atrs = {}
    ltf_dict = {}
    all_data = {}

    swan = RiskManager.check_black_swan()

    # Pass 1: Gather all data first to avoid Correlation Veto edge cases
    for category, sym_list in TICKERS.items():
        for ticker in sym_list:
            data = DataEngine.fetch_mtf_data(ticker)
            if not data:
                continue

            ltf_dict[ticker] = data['LTF']
            df_with_features = Strategy.add_features(data['LTF'])

            if df_with_features.empty or 'ATR' not in df_with_features.columns:
                continue

            current_prices[ticker] = df_with_features['Close'].iloc[-1]
            current_atrs[ticker] = df_with_features['ATR'].iloc[-1]
            all_data[ticker] = (data, df_with_features, category)

    # Pass 2: Signal Generation & Execution
    for ticker, (data, df_with_features, category) in all_data.items():
        if not tg.is_paused and not swan:

            if RiskManager.check_z_score_anomaly(ticker, data['LTF']):
                continue

            signal = Strategy.generate_signal(data['HTF'], data['LTF'])
            if signal:
                current_atrs[ticker] = signal['atr']

                # Filtre Hattı
                if RiskManager.check_correlation_veto(ticker, ltf_dict):
                    continue

                # Özellikler sözlüğünü hazırla (ML Validator için)
                features = {'EMA_50': 0, 'RSI_14': 0}
                if 'EMA_50' in df_with_features.columns and 'RSI_14' in df_with_features.columns:
                    features = {
                        'EMA_50': df_with_features['EMA_50'].iloc[-1],
                        'RSI_14': df_with_features['RSI_14'].iloc[-1]
                    }

                if not ml.validate(features, signal['dir']):
                    continue
                if nlp.get_sentiment_veto(signal['dir']):
                    continue

                # Kelly Lot Hesaplama
                try:
                    equity = INITIAL_CAPITAL + pd.read_sql_query("SELECT SUM(pnl) as tpnl FROM trades", db.conn)['tpnl'].fillna(0).iloc[0]
                except Exception as e:
                    log.error(f"Failed to fetch equity: {e}")
                    equity = INITIAL_CAPITAL

                lot = (equity * RiskManager.calculate_fractional_kelly()) / (signal['atr'] * 1.5)

                if lot > 0:
                    sl_dist = signal['atr'] * 1.5
                    sl = signal['price'] - sl_dist if signal['dir'] == 'LONG' else signal['price'] + sl_dist
                    tp = signal['price'] + (sl_dist * 2) if signal['dir'] == 'LONG' else signal['price'] - (sl_dist * 2)

                    broker.place_order(ticker, signal['dir'], signal['price'], sl, tp, lot, category)
                    await tg.send_msg(f"🎯 YENİ İŞLEM:\n{ticker} {signal['dir']}\nLot: {lot:.2f}\nGiriş: {signal['price']:.4f}\nSL: {sl:.4f}")

    # Yönetimi Tüm Evren Tarandıktan Sonra Yap
    RiskManager.manage_positions(broker, current_prices, current_atrs, swan)

    # Hafıza Yönetimi
    del ltf_dict
    del all_data
    gc.collect()

async def send_weekly_report():
    log.info("Haftalık Rapor Hazırlanıyor...")
    Analyzer.generate_tear_sheet()
    try:
        await tg.send_document("tear_sheet.html", "📊 ED Capital Haftalık Performans Raporu")
        await tg.send_document("equity_curve.png", "")
        await tg.send_document("monte_carlo.png", "")
    except Exception as e:
        log.error(f"Rapor gönderilemedi: {e}")

async def retrain_ml_model():
    log.info("Hafta Sonu ML Modeli Yeniden Eğitiliyor (Phase 18)...")
    try:
        data = DataEngine.fetch_mtf_data("GC=F")
        if data and not data['HTF'].empty:
            ml.train_if_needed(data['HTF'], force=True)
            await tg.send_msg("🧠 ML Modeli yeni verilerle başarıyla eğitildi.")
    except Exception as e:
        log.error(f"ML Retraining Error: {e}")

def schedule_jobs():
    # ML Retraining Cumartesi (Saturday)
    schedule.every().saturday.at("12:00").do(lambda: asyncio.create_task(retrain_ml_model()))

    # Tear Sheet Cuma aksami (Friday evening)
    schedule.every().friday.at("23:00").do(lambda: asyncio.create_task(send_weekly_report()))

    # Wrap async functions for schedule using asyncio.create_task within the main loop
    schedule.every().hour.at(":01").do(lambda: asyncio.create_task(run_live_cycle()))

    # Heartbeat
    schedule.every().day.at("08:00").do(lambda: asyncio.create_task(
        tg.send_msg("🟢 Sistem Aktif: Son 24 saat döngüsü tamamlandı.")
    ))

async def main():
    await tg.start(run_live_cycle_ref=run_live_cycle)
    await tg.send_msg("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.")

    schedule_jobs()

    # Ensure there's an active event loop for schedule to create tasks in
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot manuel olarak durduruldu.")
