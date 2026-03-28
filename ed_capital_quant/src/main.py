import asyncio
import logging
import gc
import os
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, logger, UNIVERSE
from core_engine import DatabaseManager, PaperBroker
from data_processor import DataLoader, FeatureEngineer, MacroRegimeFilter, SentimentFilter
from quant_models import MLValidator, PortfolioManager
from analytics import Reporter

# Global State
IS_PAUSED = False
LAST_HEARTBEAT = datetime.min
SCANS_TODAY = 0
API_ERRORS_TODAY = 0

class QuantEngine:
    def __init__(self):
        self.db = DatabaseManager()
        self.broker = PaperBroker(self.db)
        self.data_loader = DataLoader()
        self.ml_validator = MLValidator()
        self.portfolio_manager = PortfolioManager(self.db)
        self.reporter = Reporter(self.db)
        self.app: Application = None

    async def init_telegram(self):
        """Initializes the Telegram Application for two-way communication."""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not found in .env. Cannot start Telegram Bot.")
            return

        self.app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

        # Command Handlers
        self.app.add_handler(CommandHandler("start", self.cmd_start))
        self.app.add_handler(CommandHandler("durum", self.cmd_status))
        self.app.add_handler(CommandHandler("durdur", self.cmd_pause))
        self.app.add_handler(CommandHandler("devam", self.cmd_resume))
        self.app.add_handler(CommandHandler("tara", self.cmd_force_scan))
        self.app.add_handler(CommandHandler("rapor", self.cmd_report))
        self.app.add_handler(CommandHandler("kapat_hepsi", self.cmd_panic_close))

        # Security Filter: Reject non-admins
        if ADMIN_CHAT_ID:
            self.app.add_handler(MessageHandler(filters.ALL & ~filters.User(user_id=int(ADMIN_CHAT_ID)), self.unauthorized))

        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        await self.send_telegram_message("🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı.\nSistem 7/24 Aktif.")

    async def unauthorized(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.critical(f"Yetkisiz Erişim Denemesi: {update.effective_user.id}")

    async def send_telegram_message(self, text: str):
        if self.app and ADMIN_CHAT_ID:
            try:
                await self.app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Telegram failed: {e}")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("ED Capital Engine commands:\n/durum\n/durdur\n/devam\n/tara\n/rapor\n/kapat_hepsi")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        balance = self.broker.get_account_balance()
        open_trades = self.broker.get_open_positions()

        msg = f"🟢 <b>SİSTEM DURUMU</b>\n"
        msg += f"Duraklatıldı mı: {'Evet' if IS_PAUSED else 'Hayır'}\n"
        msg += f"Güncel Kasa: ${balance:,.2f}\n"
        msg += f"Açık Pozisyonlar: {len(open_trades)}\n"

        if not open_trades.empty:
            for _, t in open_trades.iterrows():
                msg += f"• {t['direction']} {t['ticker']} @ {t['entry_price']:.4f}\n"

        await update.message.reply_text(msg, parse_mode="HTML")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global IS_PAUSED
        IS_PAUSED = True
        await update.message.reply_text("⏸️ Sistem Duraklatıldı. Sinyal taraması durdu. (Açık pozisyon takibi devam ediyor).")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        global IS_PAUSED
        IS_PAUSED = False
        await update.message.reply_text("▶️ Sistem Tekrar Aktif. Otonom tarama devrede.")

    async def cmd_force_scan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔍 Manuel Tarama Başlatılıyor...")
        asyncio.create_task(self.run_live_cycle())

    async def cmd_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📄 Rapor oluşturuluyor...")
        try:
             report_path = self.reporter.generate_tear_sheet()
             if report_path and os.path.exists(report_path):
                 with open(report_path, 'rb') as doc:
                     await self.app.bot.send_document(chat_id=ADMIN_CHAT_ID, document=doc)
             else:
                 await update.message.reply_text("Rapor oluşturulamadı (yeterli veri yok).")
        except Exception as e:
             await update.message.reply_text(f"Hata: {e}")

    async def cmd_panic_close(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚨 PANİK KAPATMASI BAŞLATILDI!")
        open_trades = self.broker.get_open_positions()
        if open_trades.empty:
            await update.message.reply_text("Kapatılacak açık pozisyon yok.")
            return

        # Fetch current prices quickly to close
        import yfinance as yf
        for _, trade in open_trades.iterrows():
            try:
                ticker_obj = yf.Ticker(trade['ticker'])
                current_price = ticker_obj.fast_info['lastPrice']
                self.broker.close_position(trade['trade_id'], trade['ticker'], trade['direction'], trade['entry_price'], current_price, trade['position_size'], 1.0)
            except Exception as e:
                logger.error(f"Panic close failed for {trade['ticker']}: {e}")

        await update.message.reply_text("Tüm pozisyonlar kapatıldı.")

    async def run_live_cycle(self):
        """Main execution pipeline (The Orchestrator)."""
        global SCANS_TODAY, API_ERRORS_TODAY
        logger.info("=== Starting Live Cycle ===")

        # 1. Fetch Macro & VIX Data (Phase 19)
        macro_data = MacroRegimeFilter.get_macro_data()
        vix_panic = MacroRegimeFilter.check_vix_circuit_breaker(macro_data)
        macro_veto = MacroRegimeFilter.get_macro_trend_veto(macro_data)

        if vix_panic:
             await self.send_telegram_message("🚨 <b>KRİTİK UYARI: VIX Devre Kesici Tetiklendi!</b>\nSistem Savunma Moduna Geçti. Yeni İşlemler Durduruldu.")
             # Fallthrough to Trade Management but skip scanning

        # 2. Update Sentiment Cache (Phase 20)
        SentimentFilter.update_sentiment()

        # 3. Fetch MTF OHLCV Data
        try:
            mtf_data = await self.data_loader.fetch_mtf_data()
            SCANS_TODAY += 1
        except Exception as e:
            API_ERRORS_TODAY += 1
            logger.error(f"Data Fetch Error: {e}")
            return

        # 4. Trade Management (Trailing Stop & Breakeven)
        await self._manage_open_trades(mtf_data, vix_panic)

        # 5. Scan for New Signals (If not paused, not in VIX panic, and limits not hit)
        if not IS_PAUSED and not vix_panic:
            if self.portfolio_manager.check_global_limits():
                 logger.info("Skipping scan: Global limits reached.")
            else:
                 await self._scan_for_signals(mtf_data, macro_veto)

        # 6. Garbage Collection
        del mtf_data
        gc.collect()
        logger.info("=== Live Cycle Complete ===")

    async def _manage_open_trades(self, mtf_data: Dict[str, Dict[str, pd.DataFrame]], is_panic: bool):
        """Evaluates Open positions for TP, SL, Trailing Stop, and Breakeven adjustments."""
        open_trades = self.broker.get_open_positions()
        if open_trades.empty:
            return

        for _, trade in open_trades.iterrows():
            ticker = trade['ticker']
            if ticker not in mtf_data:
                continue

            ltf_df = mtf_data[ticker]['ltf']
            if ltf_df.empty:
                continue

            current_price = ltf_df['close'].iloc[-1]
            current_atr = 1.0 # default

            features = FeatureEngineer.add_features(ltf_df.copy())
            if not features.empty and 'atr_14' in features.columns:
                 current_atr = features['atr_14'].iloc[-1]

            atr_multiplier = 0.5 if is_panic else 1.5

            direction = trade['direction']
            entry_price = trade['entry_price']
            sl_price = trade['sl_price']
            tp_price = trade['tp_price']
            trade_id = trade['trade_id']

            exit_triggered = False
            if direction == "Long":
                if current_price <= sl_price or current_price >= tp_price:
                    exit_triggered = True
            elif direction == "Short":
                if current_price >= sl_price or current_price <= tp_price:
                    exit_triggered = True

            if exit_triggered:
                result = self.broker.close_position(trade_id, ticker, direction, entry_price, current_price, trade['position_size'], current_atr)
                msg = f"📉 <b>İşlem Kapandı</b>: {ticker} {direction}\nÇıkış: {result['exit_price']:.4f}\nNet Kâr/Zarar: ${result['net_pnl']:.2f}"
                await self.send_telegram_message(msg)
                continue

            # Trailing Stop & Breakeven Logic (Phase 12)
            new_sl = sl_price

            if direction == "Long":
                if current_price >= entry_price + current_atr and sl_price < entry_price:
                    new_sl = entry_price
                    logger.info(f"BREAKEVEN hit for {ticker}")
                    await self.send_telegram_message(f"🔒 <b>Risk Sıfırlandı</b>: {ticker} SL seviyesi giriş fiyatına çekildi.")

                calculated_ts = current_price - (atr_multiplier * current_atr)
                if calculated_ts > new_sl:
                    new_sl = calculated_ts

            elif direction == "Short":
                if current_price <= entry_price - current_atr and sl_price > entry_price:
                    new_sl = entry_price
                    logger.info(f"BREAKEVEN hit for {ticker}")
                    await self.send_telegram_message(f"🔒 <b>Risk Sıfırlandı</b>: {ticker} SL seviyesi giriş fiyatına çekildi.")

                calculated_ts = current_price + (atr_multiplier * current_atr)
                if calculated_ts < new_sl:
                    new_sl = calculated_ts

            if new_sl != sl_price:
                 self.broker.modify_trailing_stop(trade_id, new_sl)


    async def _scan_for_signals(self, mtf_data: Dict[str, Dict[str, pd.DataFrame]], macro_veto: str):
        closes_dict = {}
        for t, data in mtf_data.items():
             if not data['htf'].empty:
                 closes_dict[t] = data['htf']['close']
        if closes_dict:
            corr_df = pd.DataFrame(closes_dict)
            self.portfolio_manager.update_correlation_matrix(corr_df)

        for ticker, data in mtf_data.items():
            ltf_df = data['ltf']
            htf_df = data['htf']

            if ltf_df.empty or htf_df.empty:
                continue

            aligned_df = FeatureEngineer.align_mtf(ltf_df, htf_df)
            features = FeatureEngineer.add_features(aligned_df)

            if features.empty or len(features) < 2:
                continue

            current_row = features.iloc[-1]
            htf_close = current_row.get('htf_close_prev', 0)
            htf_ema_50 = current_row.get('htf_ema_50_prev', 0)

            signal_direction = None
            trend_up = htf_close > htf_ema_50
            trend_down = htf_close < htf_ema_50

            from config import get_asset_class
            asset_class = get_asset_class(ticker)
            if macro_veto == "RISK_OFF" and asset_class in ["Metals", "Forex_TRY"]:
                trend_up = False
            elif macro_veto == "RISK_ON" and asset_class in ["Forex_TRY"]:
                trend_down = False

            ltf_rsi_prev = current_row['rsi_14_prev']
            ltf_rsi_prev2 = features['rsi_14'].iloc[-3] if len(features) > 2 else 50
            ltf_macd_hist_prev = current_row['macd_hist_prev']

            if trend_up:
                if (ltf_rsi_prev2 < 30 and ltf_rsi_prev >= 30) or (ltf_macd_hist_prev > 0):
                    signal_direction = "Long"

            if trend_down:
                 if (ltf_rsi_prev2 > 70 and ltf_rsi_prev <= 70) or (ltf_macd_hist_prev < 0):
                    signal_direction = "Short"

            if not signal_direction:
                continue

            if SentimentFilter.check_sentiment_veto(ticker, signal_direction):
                 continue

            if self.portfolio_manager.check_correlation_veto(ticker, signal_direction):
                 continue

            if not self.ml_validator.validate_signal(current_row):
                 continue

            logger.info(f"+++ ALL FILTERS PASSED for {ticker} {signal_direction} +++")
            current_price = current_row['close']
            current_atr = current_row['atr_14']

            if signal_direction == "Long":
                sl = current_price - (1.5 * current_atr)
                tp = current_price + (3.0 * current_atr)
            else:
                sl = current_price + (1.5 * current_atr)
                tp = current_price - (3.0 * current_atr)

            lot_size = self.portfolio_manager.calculate_kelly_position_size(ticker, current_price, sl)

            if lot_size > 0:
                trade_receipt = self.broker.place_market_order(ticker, signal_direction, current_price, sl, tp, lot_size, current_atr)

                msg = f"🚀 <b>YENİ İŞLEM (MTF & ML Onaylı)</b>\n"
                msg += f"Varlık: {ticker}\n"
                msg += f"Yön: <b>{signal_direction}</b>\n"
                msg += f"Giriş Fiyatı: {trade_receipt['entry_price']:.4f}\n"
                msg += f"Zarar Kes (SL): {sl:.4f}\n"
                msg += f"Kâr Al (TP): {tp:.4f}\n"
                msg += f"Önerilen Lot: {lot_size:.4f}"

                await self.send_telegram_message(msg)

    async def heartbeat(self):
        """Sends daily heartbeat report."""
        global SCANS_TODAY, API_ERRORS_TODAY, LAST_HEARTBEAT
        now = datetime.utcnow()
        # Simplified heartbeat condition for this loop structure
        if now.hour == 8 and now.date() > LAST_HEARTBEAT.date():
             open_trades = len(self.broker.get_open_positions())
             msg = f"🟢 <b>Günlük Sistem Raporu</b>\nSon 24 saatte {SCANS_TODAY} döngü tamamlandı.\n{API_ERRORS_TODAY} API hatası tolere edildi.\nTakip edilen açık pozisyon: {open_trades}."
             await self.send_telegram_message(msg)
             SCANS_TODAY = 0
             API_ERRORS_TODAY = 0
             LAST_HEARTBEAT = now

async def main():
    engine = QuantEngine()

    # Run telegram bot init asynchronously
    asyncio.create_task(engine.init_telegram())

    logger.info("System initialized. Starting Live Cycle loop.")

    # We use a naive sleep for demonstration.
    # In production, APScheduler would be better for precise hourly alignment.
    while True:
        await engine.heartbeat()
        await engine.run_live_cycle()

        # Sleep until the next hour
        now = datetime.utcnow()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=5, microsecond=0)
        wait_seconds = (next_hour - now).total_seconds()
        if wait_seconds < 0:
             wait_seconds = 3600 # Fallback 1 hour

        logger.info(f"Sleeping for {wait_seconds:.0f} seconds until {next_hour.strftime('%H:%M:%S')} UTC...")
        await asyncio.sleep(wait_seconds)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")
    except Exception as e:
        logger.critical(f"FATAL CRASH: {e}")
