import asyncio
import gc
import sys
from datetime import datetime
import pandas as pd

from core.logger import logger
from core.database import init_db
from core.broker import PaperBroker
from core.telegram_bot import TelegramInterface
from data_engine.config import load_environment
from data_engine.loader import DataEngine
from strategy.engine import StrategyEngine
from analysis.portfolio import PortfolioManager
from analysis.reporter import PerformanceReporter

class EDQuantEngine:
    """7/24 Otonom Çalışan Kurumsal Ana Orkestratör."""

    def __init__(self):
        # 1. Ortam ve Veritabanı
        env = load_environment()
        self.bot_token = env.get("bot_token")
        self.admin_chat_id = env.get("admin_chat_id")
        self.initial_capital = env.get("initial_capital")

        init_db()

        # 2. Modüllerin Enjeksiyonu
        self.broker = PaperBroker(initial_capital=self.initial_capital)
        self.data_engine = DataEngine()
        self.strategy_engine = StrategyEngine()
        self.portfolio_manager = PortfolioManager()
        self.reporter = PerformanceReporter(initial_capital=self.initial_capital)

        # 3. Telegram Arayüzü
        self.telegram = TelegramInterface(self.bot_token, self.admin_chat_id)
        # Telegram'dan gelen komutları (/kapat_hepsi vb.) ana motora bağlamak için Callback
        self.telegram.engine_callback = self.handle_telegram_commands

        # 4. Durum Yönetimi
        self.is_running = True
        self.cycle_count = 0
        self.scan_interval_seconds = 3600 # 1 Saat (3600 sn)

    async def initialize(self):
        """Sistemi ayağa kaldırır, Telegram'ı düzgün başlatır."""
        logger.info("ED Capital Quant Engine Başlatılıyor...")

        # ML Model İlk Eğitimi (Geçmiş verilerle eğit)
        if not self.strategy_engine.ml_validator.is_trained:
            logger.info("ML Modeli eğitilmemiş. Geçmiş veriler çekilerek eğitiliyor...")
            try:
                market_data = self.data_engine.fetch_all_market_data()
                all_features = []
                for ticker, (df_htf, df_ltf) in market_data.items():
                    if df_ltf.empty or len(df_ltf) < 200: continue
                    # Girdi özelliklerini hesapla (Phase 18'de istenen)
                    features_df = self.strategy_engine.add_features(df_ltf)

                    # Target kolonu için (Gelecek kapanış) orjinal veriden Close ekle
                    features_df['Target_Close'] = df_ltf['Close'].shift(-5) # 5 mum sonrası

                    if not features_df.empty:
                        all_features.append(features_df)

                if all_features:
                    merged_features = pd.concat(all_features).dropna()

                    feature_cols = ['RSI_14', 'ATR_14', 'EMA_50', 'EMA_200']

                    self.strategy_engine.ml_validator.train_model(merged_features, feature_cols=feature_cols)
            except Exception as e:
                logger.error(f"ML Başlangıç Eğitimi Başarısız: {e}")

        # State Recovery: Kapanıp açıldığında açık pozisyonlar var mı?
        open_positions = self.broker.get_open_positions()
        if open_positions:
            logger.info(f"STATE RECOVERY: {len(open_positions)} adet açık pozisyon bulundu ve hafızaya alındı.")

        await self.telegram.send_message(f"🚀 <b>ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.</b>\n\nBaşlangıç Bakiyesi: <b>${self.initial_capital:.2f}</b>\nAçık Pozisyon Sayısı: <b>{len(open_positions)}</b>\n\nKomutlar için /durum yazınız.")

        # Telegram polling'i GÜVENLİ başlat (python-telegram-bot v20+ standardı)
        await self.telegram.application.initialize()
        await self.telegram.application.start()
        await self.telegram.application.updater.start_polling()

    async def shutdown(self):
        logger.info("Sistem kapatılıyor. Telegram bot durduruluyor...")
        await self.telegram.application.updater.stop()
        await self.telegram.application.stop()
        await self.telegram.application.shutdown()

    async def handle_telegram_commands(self, command: str):
        """Telegram'dan gelen zorunlu komutları (Panic, Scan vb.) işler."""
        if command == "panic_close":
            # Tüm piyasayı çek (anlık fiyatlar)
            market_data = self.data_engine.fetch_all_market_data()
            current_prices = {ticker: data[1]['Close'].iloc[-1] for ticker, data in market_data.items() if not data[1].empty}
            self.broker.panic_close_all(current_prices)
            await self.telegram.send_message("✅ <b>Tüm Açık Pozisyonlar PANİK Moduyla Kapatıldı.</b> /durum yazabilirsiniz.")

        elif command == "force_scan":
            await self.run_live_cycle()
            await self.telegram.send_message("✅ <b>Zorunlu Tarama Döngüsü Tamamlandı.</b>")

    async def manage_open_positions(self, market_data: dict, current_vix: float):
        """TP/SL kontrolü, Trailing Stop ve Siyah Kuğu Çıkışları."""
        open_positions = self.broker.get_open_positions()
        if not open_positions:
            return

        current_prices = {ticker: data[1]['Close'].iloc[-1] for ticker, data in market_data.items() if not data[1].empty}

        # 1. Siyah Kuğu VIX Patlaması => Agresif Çıkış
        if current_vix > 30.0:
            logger.critical(f"VIX DEVRE KESİCİSİ AKTİF ({current_vix:.2f}) -> Açık Pozisyonlar Agresif Koruma Moduna Alınıyor!")
            # Acil Panik Çıkışı (veya dar stop) yap
            self.broker.panic_close_all(current_prices)
            await self.telegram.send_message(f"🚨 <b>KRİTİK UYARI: VIX Devre Kesici Tetiklendi ({current_vix:.2f})!</b>\n\nSistem Savunma Moduna Geçti. Açık işlemler piyasa fiyatından realize edildi.")
            return

        for pos in open_positions:
            ticker = pos["ticker"]
            if ticker not in current_prices: continue

            trade_id = pos["trade_id"]
            direction = pos["direction"]
            entry_price = pos["entry_price"]
            sl_price = pos["sl_price"]
            tp_price = pos["tp_price"]
            size = pos["position_size"]
            fees = pos["fees"]
            current_price = current_prices[ticker]

            # 2. Z-Score Mikro Flaş Çöküş
            df_ltf = market_data[ticker][1]
            if self.data_engine.check_flash_crash_anomaly(df_ltf):
                logger.critical(f"[{ticker}] Z-Score Flaş Çöküşü Algılandı! İşlem derhal donduruluyor/kapatılıyor.")
                self.broker.panic_close_ticker(ticker, current_price) # Sadece o tickeri kapat
                await self.telegram.send_message(f"🚨 <b>{ticker} Flaş Çöküş Tespit Edildi!</b>\n\nAnomali koruması devreye girdi. Pozisyon likit edildi.")
                continue

            # 3. Kapanış (TP/SL) veya Trailing Stop (Kâr Koruma)
            is_closed = False
            pnl = 0.0

            # LONG KONTROL
            if direction == "Long":
                if current_price <= sl_price:
                    # SL Patladı
                    pnl = ((sl_price - entry_price) * size) - fees
                    is_closed = True
                    exit_price = sl_price
                elif current_price >= tp_price:
                    # TP Vurdu
                    pnl = ((tp_price - entry_price) * size) - fees
                    is_closed = True
                    exit_price = tp_price
                else:
                    # Trailing Stop Revizyonu (Fiyat lehimize gitti mi?)
                    atr = df_ltf['ATR_14'].iloc[-1]
                    new_sl = current_price - (1.5 * atr)
                    # Sadece eskisinden DAHA İYİ (Yüksek) ise güncelle (Strictly Monotonic)
                    if new_sl > sl_price and current_price > entry_price:
                        self.broker.modify_trailing_stop(trade_id, new_sl)
                        if sl_price < entry_price and new_sl >= entry_price:
                            # Breakeven'a çekildi
                            await self.telegram.send_message(f"🔒 <b>RİSK SIFIRLANDI</b>: {ticker} (Long)\nSL seviyesi giriş fiyatının üzerine çekildi ({new_sl:.4f}).")

            # SHORT KONTROL
            else:
                if current_price >= sl_price:
                    # SL Patladı (Short'ta SL yukarıdadır)
                    pnl = ((entry_price - sl_price) * size) - fees
                    is_closed = True
                    exit_price = sl_price
                elif current_price <= tp_price:
                    # TP Vurdu
                    pnl = ((entry_price - tp_price) * size) - fees
                    is_closed = True
                    exit_price = tp_price
                else:
                    # Trailing Stop Revizyonu (Fiyat lehimize düştü mü?)
                    atr = df_ltf['ATR_14'].iloc[-1]
                    new_sl = current_price + (1.5 * atr)
                    # Sadece eskisinden DAHA İYİ (Düşük) ise güncelle
                    if new_sl < sl_price and current_price < entry_price:
                        self.broker.modify_trailing_stop(trade_id, new_sl)
                        if sl_price > entry_price and new_sl <= entry_price:
                            # Breakeven
                            await self.telegram.send_message(f"🔒 <b>RİSK SIFIRLANDI</b>: {ticker} (Short)\nSL seviyesi giriş fiyatının altına çekildi ({new_sl:.4f}).")

            # Eğer pozisyon kapandıysa
            if is_closed:
                self.broker.close_position(trade_id, exit_price, pnl)
                # Telegram Bildirimi
                emoji = "✅ KÂR" if pnl > 0 else "❌ ZARAR"
                msg = f"{emoji} <b>İŞLEM KAPANDI: {ticker} ({direction})</b>\n"
                msg += f"Çıkış Fiyatı: {exit_price:.4f}\n"
                msg += f"<b>Net PnL: ${pnl:.2f}</b>\n"
                await self.telegram.send_message(msg)


    async def run_live_cycle(self):
        """Asıl işi yapan (Veri Çek -> Çıkışları Kontrol Et -> Yeni Sinyal Ara) döngü adımı."""
        logger.info(f"DÖNGÜ BAŞLADI (Cycle: {self.cycle_count})")

        # 1. Makro ve Evren Verilerini Çek
        macro_data = self.data_engine.fetch_macro_data()
        current_vix = self.data_engine.current_vix
        market_data = self.data_engine.fetch_all_market_data()

        if not market_data:
            logger.error("Veri çekilemedi. Döngü atlanıyor.")
            return

        # 2. Önce Açık Pozisyonları Kontrol Et (Hayatta Kalma)
        await self.manage_open_positions(market_data, current_vix)

        # 3. Yeni Sinyal Arama (Kullanıcı /durdur demediyse ve Kapasite Dolmadıysa)
        if self.telegram.is_paused:
            logger.info("Sistem duraklatılmış (Paused). Yeni sinyal aranmıyor.")
            return

        current_capital = self.broker.get_account_balance()
        open_positions_df = self.broker.get_open_positions_df()

        # Global Exposure Limiti Kontrolü
        if self.portfolio_manager.global_limit_veto(open_positions_df, current_capital):
            return

        # Korelasyon Matrisini Güncelle
        corr_matrix = self.portfolio_manager.calculate_correlation_matrix(market_data)

        # Geçmiş PNL Verisini Çek (Kelly Kriteri İçin)
        past_trades_df = fetch_dataframe("SELECT pnl FROM trades WHERE status = 'Closed'")
        kelly_fraction = self.strategy_engine.quant_math.calculate_kelly_fraction(past_trades_df)

        for ticker, (df_htf, df_ltf) in market_data.items():
            # Asenkron Sinyal ve NLP Veto Onayından Geçen Sinyal
            signal_data = await self.strategy_engine.generate_signal_async(df_htf, df_ltf, ticker, current_vix)

            if signal_data.get("signal", 0) != 0:
                direction = signal_data["direction"]
                entry_price = signal_data["entry_price"]
                sl_price = signal_data["sl_price"]
                tp_price = signal_data["tp_price"]
                fees = signal_data["fees"]

                # Korelasyon Vetosu (Riski Duplike Ediyor mu?)
                if self.portfolio_manager.correlation_veto(ticker, direction, open_positions_df, corr_matrix):
                    continue # Veto yedi, diğer tickera geç

                # Her Şey Kusursuz: Lot Hesapla ve Emri İlet
                position_size = self.strategy_engine.quant_math.calculate_position_size(
                    current_capital, kelly_fraction, entry_price, sl_price
                )

                # Çok düşük lot veya Kelly Negatifse iptal
                if position_size <= 0.0001:
                    logger.warning(f"İşlem Lotu (Position Size) 0 veya çok düşük. [{ticker}] Emri iptal edildi.")
                    continue

                receipt = self.broker.place_market_order(
                    ticker, direction, position_size, entry_price, sl_price, tp_price, fees
                )

                if receipt.get("status") == "Success":
                    msg = f"🟢 <b>YENİ AÇIK POZİSYON: {ticker}</b>\n\n"
                    msg += f"Yön: <b>{direction}</b>\n"
                    msg += f"Giriş: {entry_price:.4f}\n"
                    msg += f"SL: {sl_price:.4f} | TP: {tp_price:.4f}\n"
                    msg += f"Önerilen Lot: {position_size:.4f}\n"
                    msg += f"Kesilen Kayma/Spread Maliyeti: ${fees:.2f}\n"
                    msg += f"Fractional Kelly Oranı: %{kelly_fraction*100:.2f}\n"
                    await self.telegram.send_message(msg)

        # 4. Çöp Toplama (Garbage Collection & Bellek Temizliği)
        del market_data
        del macro_data
        gc.collect()

        logger.info(f"DÖNGÜ TAMAMLANDI (Sonraki tarama için saat başı bekleniyor)")

    async def run_forever(self):
        """Mum Kapanış Senkronizasyonu ile Sonsuz Döngü."""
        await self.initialize()

        while self.is_running:
            try:
                # Kesin Mum Kapanışı Senkronizasyonu (Candle-Close Sync)
                now = datetime.now()
                # Saatin tam başına (örn 14:00:00) ne kadar dakika ve saniye kaldığını hesapla
                minutes_to_next_hour = 59 - now.minute
                seconds_to_next_minute = 60 - now.second

                # Tam saat başını beklemek için asenkron uyku (Drift önleyici)
                sleep_duration = (minutes_to_next_hour * 60) + seconds_to_next_minute

                # Sadece ilk açılışta beklememek için ufak bir hile:
                if self.cycle_count == 0:
                    sleep_duration = 0
                else:
                    logger.info(f"Mum kapanışı bekleniyor. {sleep_duration} saniye sonra tarama yapılacak (Saat Başı).")
                    await asyncio.sleep(sleep_duration)

                # Tarama
                await self.run_live_cycle()
                self.cycle_count += 1

                # Haftasonu Pazar gecesi (weekday() == 6) model yeniden eğitilebilir ve rapor yollanabilir
                now = datetime.now() # İşlem sonrasi saati kontrol et
                if now.weekday() == 6 and now.hour == 23 and self.cycle_count > 0:
                    logger.info("HAFTALIK BAKIM: ML modeli yeniden eğitiliyor ve rapor Telegram'a yollanıyor.")

                    market_data = self.data_engine.fetch_all_market_data()
                    all_features = []
                    for ticker, (df_htf, df_ltf) in market_data.items():
                        if df_ltf.empty or len(df_ltf) < 200: continue
                        features_df = self.strategy_engine.add_features(df_ltf)
                        features_df['Target_Close'] = df_ltf['Close'].shift(-5)
                        if not features_df.empty:
                            all_features.append(features_df)
                    if all_features:
                        merged_features = pd.concat(all_features).dropna()
                        feature_cols = ['RSI_14', 'ATR_14', 'EMA_50', 'EMA_200']
                        self.strategy_engine.ml_validator.train_model(merged_features, feature_cols=feature_cols)

                    report_path = self.reporter.generate_tear_sheet()
                    await self.telegram.send_document(report_path)

            except Exception as e:
                logger.critical(f"ANA DÖNGÜDE KRİTİK HATA: {e}")
                await self.telegram.send_message(f"🚨 <b>ANA DÖNGÜ ÇÖKTÜ:</b>\n\n{e}\n\nSistem 1 dakika sonra tekrar deneyecek.")
                await asyncio.sleep(60) # Crash backoff


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    engine = EDQuantEngine()
    try:
        asyncio.run(engine.run_forever())
    except KeyboardInterrupt:
        logger.info("Kullanıcı tarafından durduruldu (KeyboardInterrupt).")
        asyncio.run(engine.shutdown())