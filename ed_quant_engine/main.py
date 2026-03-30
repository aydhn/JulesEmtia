import asyncio
import schedule
import time
import os
import signal
import gc
from datetime import datetime, timezone
import warnings
warnings.filterwarnings('ignore')

from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update

from core.infrastructure import logger, PaperDB, PaperBroker, TelegramNotifier
from core.config import ADMIN_CHAT_ID, TELEGRAM_BOT_TOKEN
from core.data_engine import DataEngine, SentimentEngine
from core.quant_models import add_features, RiskManager, MLValidator
from core.reporter import Reporter
from core.config import TICKERS, GLOBAL_EXPOSURE_LIMIT

# ----------------- GLOBALS & STATE (Phases 8, 17, 23) -----------------
system_paused = False
vix_circuit_breaker_active = False
paper_db = PaperDB()
broker = PaperBroker(paper_db) # SOLID Phase 24
risk_manager = RiskManager(paper_db)
data_engine = DataEngine(TICKERS)
sentiment_engine = SentimentEngine()
ml_validator = MLValidator()
telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, str(ADMIN_CHAT_ID))
reporter = Reporter(paper_db)

# ----------------- TELEGRAM COMMANDS (Phase 17) -----------------
async def auth_check(update: Update) -> bool:
    if update.effective_chat.id != ADMIN_CHAT_ID:
        logger.critical(f"Unauthorized access attempt from {update.effective_chat.id}")
        return False
    return True

async def cmd_durum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    balance = broker.get_account_balance()
    open_trades = broker.get_open_positions()
    msg = f"📊 *Durum Raporu*\nGüncel Bakiye: ${balance:.2f}\nAçık Pozisyonlar: {len(open_trades)}/{GLOBAL_EXPOSURE_LIMIT}\nVIX Devre Kesici: {'Aktif' if vix_circuit_breaker_active else 'Pasif'}\nTarama Durumu: {'Duraklatıldı' if system_paused else 'Aktif'}"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def cmd_durdur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    global system_paused
    system_paused = True
    logger.info("System paused via Telegram.")
    await update.message.reply_text("⏸ Sistem duraklatıldı. Açık pozisyon takibi devam edecek, yeni sinyal aranmayacak.")

async def cmd_devam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    global system_paused
    system_paused = False
    logger.info("System resumed via Telegram.")
    await update.message.reply_text("▶ Sistem devam ediyor. Taramalar aktif.")

async def cmd_kapat_hepsi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    open_trades = broker.get_open_positions()
    logger.critical("PANIC BUTTON TRIGGERED: Closing all open positions.")
    for _, trade in open_trades.iterrows():
        # Fallback closure (using entry price for demo panic close, real scenario fetches live price)
        broker.close_position(trade['trade_id'], trade['entry_price'], 0.0)
    await update.message.reply_text("🚨 Tüm açık pozisyonlar acil durum protokolüyle kapatıldı!")

async def cmd_tara(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await auth_check(update): return
    await update.message.reply_text("🔍 Manuel tarama (Force Scan) başlatılıyor...")
    asyncio.create_task(run_live_cycle())


# ----------------- CORRELATION MATRIX (Phase 11) -----------------
async def build_correlation_matrix() -> pd.DataFrame:
    close_prices = {}
    for cat, tickers in TICKERS.items():
        for ticker in tickers:
            try:
                # 30 day lookback for correlation
                df = await asyncio.to_thread(lambda t=ticker: data_engine._fetch_yf_data(t, "1d", "3mo"))
                if df is not None and not df.empty:
                    close_prices[ticker] = df['Close']
            except:
                continue

    if not close_prices:
        return pd.DataFrame()

    price_df = pd.DataFrame(close_prices)
    # Calculate daily returns
    returns = price_df.pct_change().dropna()
    # Pearson correlation
    corr_matrix = returns.corr()
    return corr_matrix

# ----------------- CORE PIPELINE (Phase 23) -----------------
async def run_live_cycle():
    """Main Orchestration Pipeline."""
    global system_paused, vix_circuit_breaker_active
    logger.info(f"--- Starting Live Cycle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    # 1. State Recovery & Open Position Management (Phases 8, 12)
    open_trades = broker.get_open_positions()
    logger.info(f"Recovered {len(open_trades)} open positions.")

    for _, trade in open_trades.iterrows():
        ticker = trade['ticker']
        # Light fetch for current price
        try:
            current_data = await asyncio.to_thread(lambda: data_engine._fetch_yf_data(ticker, "1h", "1d"))
            if current_data is not None and not current_data.empty:
                current_price = current_data['Close'].iloc[-1]
                atr = current_data['Close'].iloc[-1] * 0.01 # Fallback approximation if ta missing

                # Check TP / SL hits
                if trade['direction'] == "Long":
                    if current_price <= trade['sl_price'] or current_price >= trade['tp_price']:
                        pnl = (current_price - trade['entry_price']) * trade['position_size']
                        broker.close_position(trade['trade_id'], current_price, pnl)
                        telegram.send_message(f"✅ İşlem Kapandı: {ticker} Long @ {current_price:.4f} | PnL: ${pnl:.2f}")
                        continue
                else: # Short
                    if current_price >= trade['sl_price'] or current_price <= trade['tp_price']:
                        pnl = (trade['entry_price'] - current_price) * trade['position_size']
                        broker.close_position(trade['trade_id'], current_price, pnl)
                        telegram.send_message(f"✅ İşlem Kapandı: {ticker} Short @ {current_price:.4f} | PnL: ${pnl:.2f}")
                        continue

                # Modify Trailing Stop
                new_sl = risk_manager.calculate_trailing_stop(trade['direction'], current_price, trade['entry_price'], trade['sl_price'], atr)
                if new_sl != trade['sl_price']:
                    broker.modify_trailing_stop(trade['trade_id'], new_sl)

        except Exception as e:
            logger.error(f"Error managing position {trade['trade_id']} for {ticker}: {e}")

    # Build correlation matrix dynamically (Phase 11)
    logger.info("Building Dynamic Correlation Matrix...")
    corr_matrix = await build_correlation_matrix()

    # If paused or max exposure reached, skip new signal generation
    if system_paused:
        logger.info("System is paused. Skipping signal generation.")
        gc.collect()
        return

    if len(open_trades) >= GLOBAL_EXPOSURE_LIMIT:
        logger.info("Global exposure limit reached. Skipping signal generation.")
        gc.collect()
        return

    # 2. VIX Circuit Breaker (Phase 19)
    macro_dfs = await data_engine.fetch_macro_data()
    vix_df = macro_dfs.get('^VIX')
    if vix_df is not None and not vix_df.empty:
        current_vix = vix_df['Close'].iloc[-1]
        logger.info(f"Current VIX: {current_vix:.2f}")
        if current_vix > 35.0: # Black Swan Panic Level
            vix_circuit_breaker_active = True
            logger.critical(f"VIX Circuit Breaker Activated ({current_vix:.2f}). Halting new trades.")
            telegram.send_message("🚨 KRİTİK UYARI: VIX Devre Kesici Tetiklendi! Sistem Savunma Moduna Geçti. Yeni İşlemler Durduruldu.")
            gc.collect()
            return
    vix_circuit_breaker_active = False

    # 3. Market Scan & Signal Generation (Phases 3, 4, 11, 15, 16, 18, 20)
    for category, ticker_list in TICKERS.items():
        for ticker in ticker_list:
            try:
                # MTF Fetching & Alignment (Phase 16)
                df_htf, df_ltf = await data_engine.fetch_mtf_data(ticker)
                if df_htf is None or df_ltf is None: continue

                df_htf_features = add_features(df_htf)
                df_ltf_features = add_features(df_ltf)

                if df_htf_features.empty or df_ltf_features.empty: continue

                # Align daily to hourly to prevent lookahead
                aligned_df = data_engine.align_mtf_data(df_htf_features, df_ltf_features)
                if aligned_df.empty: continue

                # Signal Logic (Phase 4 & 16)
                last_row = aligned_df.iloc[-1]
                prev_row = aligned_df.iloc[-2] # Confirm on closed hourly candle

                # MICRO FLASH CRASH VETO (Phase 19 Z-Score)
                current_z_score = last_row['Z_Score']
                if abs(current_z_score) >= 4.0:
                    logger.critical(f"FLASH CRASH HALT: {ticker} Z-Score is {current_z_score:.2f} (Anomaly). Rejecting all signals.")
                    continue

                # HTF Daily Trend Filter
                htf_trend_up = last_row['HTF_Close'] > last_row['HTF_EMA_50']
                htf_trend_down = last_row['HTF_Close'] < last_row['HTF_EMA_50']

                # LTF Hourly Entry Trigger
                ltf_rsi_bullish = prev_row['RSI_14'] < 30 and last_row['RSI_14'] >= 30
                ltf_rsi_bearish = prev_row['RSI_14'] > 70 and last_row['RSI_14'] <= 70

                direction = None
                if htf_trend_up and ltf_rsi_bullish:
                    direction = "Long"
                elif htf_trend_down and ltf_rsi_bearish:
                    direction = "Short"

                if not direction:
                    continue # No Signal

                logger.info(f"Technical Signal Found: {ticker} {direction}")

                # VETO 1: Machine Learning (Phase 18)
                if not ml_validator.validate_signal(aligned_df, direction):
                    continue

                # VETO 2: News Sentiment (Phase 20)
                sentiment_score = await sentiment_engine.fetch_sentiment(category)
                if (direction == "Long" and sentiment_score < -0.5) or (direction == "Short" and sentiment_score > 0.5):
                    logger.warning(f"Sentiment Veto: {ticker} {direction} (Score: {sentiment_score:.2f})")
                    continue

                # VETO 3: Correlation Matrix (Phase 11)
                if not corr_matrix.empty:
                    if not risk_manager.check_portfolio_limits(ticker, direction, corr_matrix):
                        continue

                # Execution (Phase 15, 21, 24)
                current_price = last_row['Close']
                atr = last_row['ATRr_14']

                # Dynamic ATR SL/TP
                sl_price = current_price - (1.5 * atr) if direction == "Long" else current_price + (1.5 * atr)
                tp_price = current_price + (3.0 * atr) if direction == "Long" else current_price - (3.0 * atr)

                balance = broker.get_account_balance()
                lot_size = risk_manager.calculate_position_size(current_price, atr, balance)

                if lot_size <= 0:
                    logger.warning(f"Kelly constraint failed lot size for {ticker}")
                    continue

                spread, slippage = risk_manager.dynamic_spread_slippage(ticker, current_price, atr)

                # PLACE ORDER
                receipt = broker.place_market_order(ticker, direction, lot_size, sl_price, tp_price, current_price, spread, slippage)

                # Notify
                msg = f"🚀 *Yeni Sinyal: {ticker}*\n"
                msg += f"Yön: {direction}\n"
                msg += f"Giriş: {receipt['entry_price']:.4f}\n"
                msg += f"SL: {sl_price:.4f} | TP: {tp_price:.4f}\n"
                msg += f"Lot: {lot_size:.4f} (Kelly)\n"
                telegram.send_message(msg)

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")

    # Memory Management (Phase 23)
    gc.collect()
    logger.info("--- Cycle Complete ---")


# ----------------- SCHEDULED BACKGROUND TASKS (Phases 8, 13, 18) -----------------
def daily_heartbeat():
    open_trades = broker.get_open_positions()
    msg = f"🟢 *Sistem Aktif (Heartbeat)*\n"
    msg += f"Kasa: ${broker.get_account_balance():.2f}\n"
    msg += f"Açık Pozisyon: {len(open_trades)}\n"
    telegram.send_message(msg)

def weekly_tear_sheet():
    logger.info("Generating Weekly Tear Sheet...")
    try:
        report_path = reporter.generate_tear_sheet()
        if report_path.endswith(".html"):
            telegram.send_message("📊 Haftalık Tear Sheet (HTML) oluşturuldu.")
            # In a real scenario with Pyrogram/TelegramBot, send Document.
            # telegram.send_document(report_path)
    except Exception as e:
        logger.error(f"Error generating tear sheet: {e}")

def weekly_ml_retrain():
    logger.info("Retraining ML Model (Phase 18)...")
    try:
        # Fetch long term history for a major ticker (e.g. GC=F) as a proxy,
        # or aggregate across universe. We use Gold for now.
        import yfinance as yf
        from core.quant_models import add_features
        hist_df = yf.Ticker("GC=F").history(period="1y", interval="1d")
        hist_df = add_features(hist_df)
        ml_validator.train(hist_df)
        telegram.send_message("🧠 ML Modeli başarıyla yeniden eğitildi.")
    except Exception as e:
        logger.error(f"Error retraining ML model: {e}")

# Register schedule jobs
schedule.every().day.at("08:00").do(daily_heartbeat)
schedule.every().friday.at("23:50").do(weekly_tear_sheet)
schedule.every().saturday.at("10:00").do(weekly_ml_retrain)

# ----------------- BACKGROUND SCHEDULER (Phase 9) -----------------
async def scheduled_loop():
    """Run `run_live_cycle` strictly on the hour."""
    telegram.send_message("🟢 *ED Capital Quant Engine Canlı Modda Başlatıldı.*")
    while True:
        schedule.run_pending()
        now = datetime.now()
        # Trigger on top of the hour (e.g., 14:00:00)
        if now.minute == 0 and now.second < 10:
            await run_live_cycle()
            await asyncio.sleep(60) # Prevent multiple triggers in the same minute
        await asyncio.sleep(1)

# ----------------- MAIN BOOTSTRAP -----------------
if __name__ == "__main__":
    logger.info("Starting ED Capital Quant Engine...")

    # Initialize DB and Broker
    logger.info(f"Initial Balance: ${broker.get_account_balance():.2f}")

    # Setup Telegram Application (Polling mode - non-blocking via asyncio in v20+)
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("durum", cmd_durum))
    application.add_handler(CommandHandler("durdur", cmd_durdur))
    application.add_handler(CommandHandler("devam", cmd_devam))
    application.add_handler(CommandHandler("kapat_hepsi", cmd_kapat_hepsi))
    application.add_handler(CommandHandler("tara", cmd_tara))

    loop = asyncio.get_event_loop()

    # Start Telegram polling
    # Correctly initialize and start python-telegram-bot v20+ in an existing asyncio loop
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())
    loop.run_until_complete(application.updater.start_polling())

    # Start the Trading loop
    try:
        loop.run_until_complete(scheduled_loop())
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    finally:
        loop.close()
