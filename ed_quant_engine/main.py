"""
ED Capital Quant Engine - Otonom İşlem Motoru (Main Loop)
Vizyon: SIFIR BÜTÇE, Katı Kurumsal Algoritmalar, Yüksek Win Rate.
Bu dosya sistemin kalbidir ve docker-compose veya systemd üzerinden 7/24 çalışır.
"""
import asyncio
import schedule
import time
import os
import gc
from datetime import datetime, timedelta
import pandas as pd
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from src.config import get_all_tickers, VIX_CIRCUIT_BREAKER
from src.logger import log_info, log_error, log_warning, log_critical
from src.data_loader import load_universe_mtf, fetch_data_sync
from src.features import add_features, merge_mtf_data
from src.strategy import analyze_signals
from src.macro_filter import check_black_swan, check_flash_crash, get_market_regime
from src.portfolio_manager import PortfolioManager
from src.broker import PaperBroker
from src.execution_model import apply_execution_costs
import src.notifier as nt

# Global Nesneler
broker = PaperBroker()
portfolio_manager = PortfolioManager()

# --- ARKA PLAN (Background) GÖREVLERİ ---
def retrain_ml_models():
    """Haftalık (Pazar günleri) otonom makine öğrenmesi yeniden eğitimi."""
    log_info("🤖 Haftalık ML Modelleri Yeniden Eğitiliyor...")
    from src.ml_validator import train_and_save_model
    tickers = get_all_tickers()
    for ticker in tickers:
        df_htf = fetch_data_sync(ticker, period="2y", interval="1d")
        df_ltf = fetch_data_sync(ticker, period="60d", interval="1h")

        if df_htf is not None and df_ltf is not None:
            df_htf_feat = add_features(df_htf, is_htf=True)
            df_ltf_feat = add_features(df_ltf, is_htf=False)
            df_merged = merge_mtf_data(df_ltf_feat, df_htf_feat)
            train_and_save_model(ticker, df_merged)
    log_info("🤖 ML Eğitim Süreci Tamamlandı.")

def daily_heartbeat():
    """Günlük canlılık sinyali (Her sabah 08:00)."""
    balance = broker.get_account_balance()
    trades = broker.get_open_positions()
    msg = f"🟢 <b>SİSTEM AKTİF (Heartbeat)</b>\nKasa: <b>${balance:,.2f}</b>\nTakip Edilen Açık İşlem: <b>{len(trades)}</b>\nSiyah Kuğu / VIX: Normal"
    nt.send_telegram_message(msg)

def weekly_report():
    """Cuma akşamı kurumsal rapor (Tear Sheet) gönderimi."""
    from src.reporter import generate_tear_sheet
    file_path = generate_tear_sheet()
    if file_path:
        asyncio.run(nt.send_document(file_path, caption="ED Capital Haftalık Yönetim Özeti"))
    log_info("📄 Haftalık Tear Sheet gönderildi.")

# --- ANA İŞLEM DÖNGÜSÜ (Trading Loop) ---
async def execute_trading_cycle():
    """
    Her saat başı veya manuel tetiklenen tam tur tarama ve yönetim döngüsü.
    Adımlar:
    1. Açık İşlemleri Yönet (Kâr Al, Zarar Kes, İzleyen Stop, Siyah Kuğu Acil Çıkış)
    2. Manuel Müdahale veya Panik Butonu (kapat_hepsi) var mı?
    3. MTF Veri Çek ve Korelasyon Matrisini Güncelle
    4. Makro Filtreler (VIX Devre Kesici)
    5. Yeni Sinyal Ara (Strateji + ML + Sentiment + Kelly)
    6. Emir İletimi (Execution)
    """
    log_info("🔄 Canlı Ticaret Döngüsü (Trading Cycle) Başladı.")
    tickers = get_all_tickers()
    current_balance = broker.get_account_balance()

    # 1. ACİL DURUM: Kullanıcı Panik Kapatması İstedi mi? (/kapat_hepsi)
    if nt.PANIC_CLOSE:
        log_critical("🚨 PANİK KAPATMASI İŞLENİYOR! Tüm açık pozisyonlar tasfiye edilecek!")
        open_trades = broker.get_open_positions()
        for t in open_trades:
            # Anlık fiyatı (hızlıca) çek
            try:
                df = fetch_data_sync(t['ticker'], period="1d", interval="1m")
                current_price = df['Close'].iloc[-1]
                # Fallback atr
                exit_price, _, _ = apply_execution_costs(t['ticker'], "Short" if t['direction']=="Long" else "Long", current_price, current_price*0.01, current_price*0.01)
                broker.close_position(t['trade_id'], exit_price, "Panik (Kapat Hepsi)")
            except Exception as e:
                log_error(f"Acil Kapatma Hatası ({t['ticker']}): {e}")
        nt.PANIC_CLOSE = False
        nt.send_telegram_message("✅ Panik tasfiyesi tamamlandı.")
        return # Bu döngüyü sonlandır

    # MTF Veri Çekimi (Asenkron)
    universe_mtf = await load_universe_mtf(tickers)

    # İşlenmiş Verileri Tutmak İçin (Çoklu okumayı engellemek adına)
    processed_mtf = {}
    df_vix = None
    df_dxy = None
    df_tnx = None

    for ticker, data in universe_mtf.items():
        if data.get('1d') is None or data.get('1h') is None:
            continue

        # Makro verileri (VIX, DXY, TNX) ayrı tut
        if ticker == "^VIX": df_vix = data['1d']; continue
        if ticker == "DX-Y.NYB": df_dxy = data['1d']; continue
        if ticker == "^TNX": df_tnx = data['1d']; continue
        if ticker == "USDTRY=X": pass # Döviz için de features hesaplanacak

        # Özellik mühendisliği ve MTF birleştirme (Features.py)
        df_htf_feat = add_features(data['1d'], is_htf=True)
        df_ltf_feat = add_features(data['1h'], is_htf=False)
        df_merged = merge_mtf_data(df_ltf_feat, df_htf_feat)

        # Sadece son kısımları tut (Hafıza optimizasyonu)
        processed_mtf[ticker] = {
            "1d": df_htf_feat.tail(50),
            "1h": df_merged.tail(100)
        }

    # 2. VIX DEVRE KESİCİ (Black Swan Protection)
    vix_panic = False
    if df_vix is not None:
        vix_panic = check_black_swan(df_vix, VIX_CIRCUIT_BREAKER)

    if vix_panic:
        nt.send_telegram_message(f"🚨 <b>VIX DEVRE KESİCİ TETİKLENDİ!</b>\nVIX Seviyesi: {df_vix['Close'].iloc[-1]:.2f}\nYeni alımlar durduruldu, açık pozisyonlar acil koruma moduna alındı.")

    # Korelasyon Matrisini Güncelle (Son 60 gün HTF verisiyle)
    portfolio_manager.update_correlation_matrix(processed_mtf)

    # 3. AÇIK İŞLEMLERİN YÖNETİMİ (Kâr Koruma, TP/SL, Trailing Stop)
    open_trades = broker.get_open_positions()
    for trade in open_trades:
        trade_id = trade['trade_id']
        ticker = trade['ticker']
        direction = trade['direction']
        entry_price = trade['entry_price']
        sl = trade['sl_price']
        tp = trade['tp_price']

        if ticker not in processed_mtf: continue

        df_current = processed_mtf[ticker]['1h']
        current_price = df_current['Close'].iloc[-1]
        atr = df_current['ATRr_14'].iloc[-1]

        # Z-Score Anomali Koruması (Flaş Çöküş)
        if check_flash_crash(df_current):
            log_critical(f"🚨 FLAŞ ÇÖKÜŞ KORUMASI: {ticker} Anormal Fiyat Hareketi. Pozisyon acil kapatılıyor.")
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Flash Crash Halt")
            nt.send_telegram_message(f"🚨 <b>FLAŞ ÇÖKÜŞ:</b> {ticker} pozisyonu {current_price:.4f} fiyatından tasfiye edildi.")
            continue

        # VIX Paniği Varsa Agresif Çıkış (SL'yi mevcut fiyata çek, kârı kilitle)
        if vix_panic and ((direction == "Long" and current_price > entry_price) or (direction == "Short" and current_price < entry_price)):
            log_warning(f"VIX Paniği: {ticker} kârda kapatılıyor.")
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "VIX Panic Lock-In")
            nt.send_telegram_message(f"🔒 <b>VIX PANİĞİ:</b> {ticker} pozisyonu kârla kapatılarak anapara korundu.")
            continue

        # TP ve SL Vurma Kontrolü
        hit_sl = False
        hit_tp = False
        if direction == "Long":
            if current_price <= sl: hit_sl = True
            elif current_price >= tp: hit_tp = True
        else: # Short
            if current_price >= sl: hit_sl = True
            elif current_price <= tp: hit_tp = True

        if hit_sl:
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Stop-Loss Hit")
            nt.send_telegram_message(f"🔴 <b>STOP-LOSS:</b> {ticker} pozisyonu {current_price:.4f} fiyatından kapandı.")
            continue
        if hit_tp:
            exit_price, _, _ = apply_execution_costs(ticker, "Short" if direction=="Long" else "Long", current_price, atr, atr)
            broker.close_position(trade_id, exit_price, "Take-Profit Hit")
            nt.send_telegram_message(f"🟢 <b>TAKE-PROFIT:</b> {ticker} pozisyonu {current_price:.4f} hedefinden başarıyla kapandı.")
            continue

        # İZLEYEN STOP (Trailing Stop) & BAŞA BAŞ (Breakeven) KONTROLÜ
        # Fiyat lehimize %50 ATR gittiyse (Breakeven)
        # Fiyat yeni tepe yaptıysa SL'yi arkasından çek. SADECE MONOTONİK (Lehe hareket edebilir)
        new_sl = sl
        if direction == "Long":
            # Breakeven
            if current_price > entry_price + (1.0 * atr) and sl < entry_price:
                new_sl = entry_price
                log_info(f"🛡️ BREAKEVEN: {ticker} SL giriş fiyatına çekildi.")
            # Trailing
            trailing_level = current_price - (1.5 * atr)
            if trailing_level > new_sl: # Asla geri çekilemez (Monotonic strict)
                new_sl = trailing_level
        else: # Short
            if current_price < entry_price - (1.0 * atr) and sl > entry_price:
                new_sl = entry_price
                log_info(f"🛡️ BREAKEVEN: {ticker} SL giriş fiyatına çekildi.")
            trailing_level = current_price + (1.5 * atr)
            if trailing_level < new_sl:
                new_sl = trailing_level

        if new_sl != sl:
            broker.modify_trailing_stop(trade_id, new_sl)
            nt.send_telegram_message(f"🔒 <b>İZLEYEN STOP GÜNCELLENDİ:</b> {ticker} SL Seviyesi: {new_sl:.4f}")

    # 4. YENİ SİNYAL ARAMA VE EMİR İLETİMİ (Kullanıcı /durdur demediyse ve VIX normalse)
    if nt.SYSTEM_PAUSED:
        log_info("⏸️ Sistem Duraklatıldı (Paused). Yeni sinyal taraması atlandı.")
    elif vix_panic:
        log_info("🚨 VIX Siyah Kuğu Rejimi! Yeni sinyal aranmıyor, sadece savunma yapılıyor.")
    else:
        # Piyasada yeni açık işlemler listesi (Yukarıda bazıları kapanmış olabilir)
        current_open_trades = broker.get_open_positions()

        # Strateji Motoru (MTF + ML + Sentiment + Kelly dahil)
        new_signals = analyze_signals(processed_mtf, current_balance, portfolio_manager, current_open_trades)

        for sig in new_signals:
            log_info(f"🚀 ONAYLANMIŞ EMİR: {sig['ticker']} {sig['direction']} | Lot: {sig['position_size']:.4f}")

            trade_id = broker.place_market_order(
                ticker=sig['ticker'],
                direction=sig['direction'],
                qty=sig['position_size'],
                current_price=sig['entry_price'], # Maliyetler eklenmiş fiyat
                sl=sig['sl_price'],
                tp=sig['tp_price'],
                slippage=sig['slippage'],
                spread=sig['spread']
            )

            if trade_id:
                msg = f"🚀 <b>YENİ İŞLEM AÇILDI!</b>\n\n"
                msg += f"<b>Varlık:</b> {sig['ticker']}\n"
                msg += f"<b>Yön:</b> {sig['direction']}\n"
                msg += f"<b>Giriş (Net):</b> {sig['entry_price']:.4f}\n"
                msg += f"<b>SL:</b> {sig['sl_price']:.4f} | <b>TP:</b> {sig['tp_price']:.4f}\n"
                msg += f"<b>Önerilen Büyüklük:</b> {sig['position_size']:.4f} Lot/Kontrat\n"
                msg += f"<i>(Kayma/Slippage Mal.: {sig['slippage']:.5f})</i>"
                nt.send_telegram_message(msg)

    # 5. Hafıza Temizliği (Garbage Collection)
    del universe_mtf
    del processed_mtf
    gc.collect()
    log_info("✅ Döngü başarıyla tamamlandı, hafıza temizlendi.")

# --- ORKESTRASYON VE ZAMANLAYICI (Main Scheduler Loop) ---
def run_scheduler_loop():
    """
    Sistemin ana döngüsü. Python 'schedule' kütüphanesi kullanarak görevleri zamanlar.
    Asenkron asyncio event loop'unu bloklamadan, while döngüsünü işletir.
    DİKKAT: Memory leak önlemek için asyncio görevleri create_task ile eklenir.
    """
    log_info("🚀 ED Capital Quant Engine Başlatılıyor...")

    # Telegram Bot Başlat (Non-Blocking)
    app = nt.start_telegram_listener()
    if app:
        # v20+ async lifecycle
        loop = asyncio.get_event_loop()
        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.start())
        loop.run_until_complete(app.updater.start_polling())
        log_info("✅ Telegram Çift Yönlü İletişim (Webhook/Polling) Aktif.")
        nt.send_telegram_message("🚀 <b>ED Capital Quant Engine</b> Otonom Moda Geçti.\nKasa, ML Modelleri ve Algoritmalar hazır.")

    # Zamanlanmış Görevler
    schedule.every().day.at("08:00").do(daily_heartbeat)
    schedule.every().sunday.at("02:00").do(retrain_ml_models) # Hafta sonu ML Eğitimi
    schedule.every().friday.at("23:30").do(weekly_report)     # Cuma kapanış raporu

    # Ana Tarama Döngüsü: Kesin Mum Kapanışı (Candle-Close Synchronization)
    # Her saatin ilk dakikasında çalışır (Örn 14:01).
    # Bu, yfinance'in API verisini işlemesi için 1 dakika toleranstır.
    schedule.every().hour.at(":01").do(lambda: asyncio.create_task(execute_trading_cycle()))

    log_info("⏳ Zamanlayıcı (Scheduler) dinleme modunda. Sistemin saat başına ulaşması bekleniyor...")

    try:
        loop = asyncio.get_event_loop()
        # Non-blocking sonsuz döngü
        async def main_loop():
            while True:
                # Kullanıcı /tara komutu verdiyse anında çalıştır
                if nt.FORCE_SCAN:
                    log_info("Kullanıcı Tetiklemesi: Anlık Tarama yapılıyor...")
                    await execute_trading_cycle()
                    nt.FORCE_SCAN = False

                schedule.run_pending()
                await asyncio.sleep(1) # CPU Dostu uyku

        loop.run_until_complete(main_loop())
    except KeyboardInterrupt:
        log_info("🛑 Kullanıcı (veya Systemd) tarafından kapatıldı. Güvenli çıkış yapılıyor...")
    except Exception as e:
        log_critical(f"FATAL ERROR (Ana Döngü Çöktü): {e}")
        nt.send_telegram_message("❌ <b>SİSTEM ÇÖKTÜ (FATAL ERROR)</b>\nAna döngü durdu. Acil müdahale gerekiyor!")
    finally:
        if app:
            # Graceful shutdown for telegram app
            loop.run_until_complete(app.updater.stop())
            loop.run_until_complete(app.stop())
            loop.run_until_complete(app.shutdown())

if __name__ == "__main__":
    # Windows/WSL için event loop policy ayarı
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    run_scheduler_loop()
