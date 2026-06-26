from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import gc

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

from src.paths import ENV_PATH


load_dotenv(ENV_PATH)

from src.config import ALL_TICKERS, AUTO_STOP_SECONDS, get_spread
from src.data_ingestor import run_bulk_ingest
from src.data_loader import fetch_macro_data, get_mtf_data
from src.features import merge_mtf_data
from src.logger import get_logger
from src.macro_filter import check_circuit_breaker, check_flash_crash, check_macro_regime_veto
from src.ml_validator import validate_signal
from src.notifier import (
    disable_telegram,
    get_telegram_application,
    send_telegram_document,
    send_telegram_message,
    set_force_scan_callback,
    set_panic_callback,
)
from src.portfolio import calculate_correlation_matrix, check_global_limits, evaluate_signal_risk
from src.reporter import create_tear_sheet
from src.sentiment_filter import fetch_rss_sentiment
from src.strategy import generate_signals, manage_open_positions
from src.broker import PaperBroker
from src.continuous_learner import start_continuous_learner
import src.paper_db as db


logger = get_logger()
broker = PaperBroker()


async def panic_close_all() -> None:
    logger.warning("Panic close all triggered.")
    open_trades = broker.get_open_positions()
    if not open_trades:
        await send_telegram_message("Acik pozisyon bulunamadi.")
        return

    for trade in open_trades:
        ticker = trade["ticker"]
        try:
            current_data = await asyncio.to_thread(
                yf.download,
                tickers=ticker,
                period="1d",
                interval="1m",
                progress=False,
                auto_adjust=True,
            )
            if current_data.empty:
                continue
            if isinstance(current_data.columns, pd.MultiIndex):
                current_price = float(current_data["Close"][ticker].iloc[-1])
            else:
                current_price = float(current_data["Close"].iloc[-1])
            broker.close_position(int(trade["trade_id"]), current_price, exit_reason="PANIC")
        except Exception as exc:
            logger.error("Error panic closing %s: %s", ticker, exc)

    await send_telegram_message("Panik kapatma tamamlandi.")


async def run_live_cycle() -> None:
    from src.notifier import engine_paused

    logger.info("Starting live cycle.")
    macro_data = fetch_macro_data()
    black_swan = check_circuit_breaker(macro_data)
    if black_swan:
        await send_telegram_message(
            f"<b>VIX circuit breaker active</b>\n"
            f"VIX: {macro_data.get('VIX', 0):.2f}\nNew entries are paused."
        )

    df_dict: dict[str, pd.DataFrame] = {}
    price_dict: dict[str, pd.Series] = {}
    for ticker in ALL_TICKERS:
        try:
            mtf_raw = await get_mtf_data(ticker)
            if mtf_raw["ltf"].empty or mtf_raw["htf"].empty:
                logger.info("Skipping %s: missing LTF/HTF data.", ticker)
                continue
            merged_df = merge_mtf_data(mtf_raw["ltf"], mtf_raw["htf"])
            if merged_df.empty:
                logger.info("Skipping %s: insufficient feature data.", ticker)
                continue
            if check_flash_crash(merged_df):
                logger.warning("%s halted due to flash-crash anomaly.", ticker)
                continue
            df_dict[ticker] = merged_df
            price_dict[ticker] = merged_df["Close"]
        except Exception as exc:
            logger.error("Error processing %s: %s", ticker, exc, exc_info=True)

    close_receipts = manage_open_positions(broker, df_dict, black_swan)
    for receipt in close_receipts:
        await send_telegram_message(
            "<b>Paper trade closed</b>\n"
            f"Trade: #{receipt.get('trade_id')}\n"
            f"Exit: {receipt.get('execution_price', 0):.4f}\n"
            f"PnL: {receipt.get('pnl', 0):.2f}"
        )

    if black_swan or engine_paused:
        logger.info("Skipping new signals. black_swan=%s engine_paused=%s", black_swan, engine_paused)
        return

    corr_matrix = calculate_correlation_matrix(price_dict)
    current_balance = broker.get_account_balance()
    if not check_global_limits(current_balance):
        return

    sentiment_score = await fetch_rss_sentiment()
    opened = 0
    for ticker, df in df_dict.items():
        signal = generate_signals(df, ticker, current_balance, macro_data.get("Regime", "Risk-On"))
        if not signal:
            continue

        if not check_macro_regime_veto(ticker, signal["direction"], macro_data):
            continue
        if not validate_signal(ticker, signal["features"]):
            continue

        if signal["direction"] == "Long" and sentiment_score < -0.3:
            logger.info("Sentiment veto: rejected Long on %s due to negative score %.2f", ticker, sentiment_score)
            continue
        if signal["direction"] == "Short" and sentiment_score > 0.3:
            logger.info("Sentiment veto: rejected Short on %s due to positive score %.2f", ticker, sentiment_score)
            continue

        risk_decision = evaluate_signal_risk(signal, corr_matrix, current_balance)
        if not risk_decision.approved:
            logger.info("Risk veto: %s signal=%s context=%s", risk_decision.reason, ticker, risk_decision.context)
            continue

        signal["risk_pct"] = risk_decision.risk_pct
        sl_distance = abs(signal["entry_price"] - signal["sl_price"])
        signal["position_size"] = (current_balance * signal["risk_pct"] / sl_distance) if sl_distance > 0 else 0.0
        if signal["position_size"] <= 0:
            continue

        receipt = broker.place_market_order(
            ticker=signal["ticker"],
            direction=signal["direction"],
            market_price=signal["entry_price"],
            sl_price=signal["sl_price"],
            tp_price=signal["tp_price"],
            position_size=signal["position_size"],
            atr=signal["atr"],
            risk_pct=signal["risk_pct"],
            strategy_tag=signal["strategy_tag"],
            metadata={"risk_decision": risk_decision.context, "macro": macro_data},
        )
        opened += 1
        await send_telegram_message(
            "<b>New paper trade opened</b>\n"
            f"Ticker: {ticker}\nDirection: {signal['direction']}\n"
            f"Entry: {receipt['execution_price']:.4f}\n"
            f"SL: {signal['sl_price']:.4f} | TP: {signal['tp_price']:.4f}\n"
            f"Size: {signal['position_size']:.4f}\nRisk: {signal['risk_pct']:.2%}"
        )

        current_balance = broker.get_account_balance()
        if not check_global_limits(current_balance):
            break

    del df_dict
    del price_dict
    gc.collect()
    logger.info("Live cycle completed. opened=%s audit=%s", opened, db.audit_trade_history())


def _seconds_until_next(target_hour: int, target_minute: int = 1) -> float:
    now = datetime.now()
    target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _seconds_until_next_hour_mark(minute: int = 1) -> float:
    now = datetime.now()
    next_run = now.replace(minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(hours=1)
    return max((next_run - now).total_seconds(), 0)


async def hourly_scheduler() -> None:
    while True:
        wait = _seconds_until_next_hour_mark(minute=1)
        logger.info("Next live cycle in %.1f minutes.", wait / 60)
        await asyncio.sleep(wait)
        await run_live_cycle()


async def daily_heartbeat_scheduler() -> None:
    cycles = 0
    while True:
        wait = _seconds_until_next(8, 0)
        await asyncio.sleep(wait)
        cycles += 1
        open_trades = len(broker.get_open_positions())
        await send_telegram_message(
            "<b>System heartbeat</b>\n"
            f"Balance: ${broker.get_account_balance():.2f}\n"
            f"Open positions: {open_trades}\n"
            f"Heartbeat cycles: {cycles}"
        )


async def weekly_report_scheduler() -> None:
    while True:
        now = datetime.now()
        days_until_friday = (4 - now.weekday()) % 7
        if days_until_friday == 0 and now.hour >= 23:
            days_until_friday = 7
        next_friday = (now + timedelta(days=days_until_friday)).replace(hour=23, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_friday - now).total_seconds())
        report_path = create_tear_sheet()
        if report_path:
            await send_telegram_document(report_path)


async def weekend_retrain_scheduler() -> None:
    while True:
        now = datetime.now()
        days_until_saturday = (5 - now.weekday()) % 7
        if days_until_saturday == 0 and now.hour >= 10:
            days_until_saturday = 7
        next_saturday = (now + timedelta(days=days_until_saturday)).replace(hour=10, minute=0, second=0, microsecond=0)
        await asyncio.sleep((next_saturday - now).total_seconds())
        logger.info("Weekend retrain marker reached; continuous learner is already active.")


async def _run_background_tasks() -> None:
    tasks = [
        asyncio.create_task(start_continuous_learner(), name="continuous_learner"),
        asyncio.create_task(hourly_scheduler(), name="hourly_scheduler"),
        asyncio.create_task(daily_heartbeat_scheduler(), name="daily_heartbeat"),
        asyncio.create_task(weekly_report_scheduler(), name="weekly_report"),
        asyncio.create_task(weekend_retrain_scheduler(), name="weekend_retrain"),
    ]
    try:
        if AUTO_STOP_SECONDS > 0:
            logger.info("Auto-stop enabled: %s seconds.", AUTO_STOP_SECONDS)
            await asyncio.sleep(AUTO_STOP_SECONDS)
            logger.info("Auto-stop elapsed; cancelling background tasks.")
        else:
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def main() -> None:
    logger.info("Initializing ED Capital Quant Engine. env=%s", ENV_PATH)
    db.init_db()
    logger.info("Paper DB audit at startup: %s", db.audit_trade_history())

    set_panic_callback(panic_close_all)
    set_force_scan_callback(run_live_cycle)

    telegram_app = get_telegram_application()
    if telegram_app:
        try:
            await telegram_app.initialize()
            await telegram_app.start()
            await telegram_app.updater.start_polling()
            logger.info("Telegram bot started.")
            await send_telegram_message("<b>ED Capital Quant Engine started.</b>")
        except Exception as exc:
            logger.warning("Telegram bot could not start: %s. Running offline.", exc)
            disable_telegram(f"startup failed: {exc}")
            telegram_app = None
    else:
        logger.warning("Telegram bot disabled or credentials missing. Running offline.")

    try:
        logger.info("Starting bulk historical data ingest.")
        await run_bulk_ingest(ALL_TICKERS)
        logger.info("Running immediate live cycle before schedulers.")
        await run_live_cycle()
        await _run_background_tasks()
    finally:
        if telegram_app:
            try:
                await telegram_app.updater.stop()
                await telegram_app.stop()
                await telegram_app.shutdown()
            except Exception as exc:
                logger.warning("Telegram shutdown warning: %s", exc)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as exc:
        logger.critical("Bot crashed: %s", exc, exc_info=True)
        raise
