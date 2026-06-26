from __future__ import annotations

import asyncio
import sqlite3

import pandas as pd
import yfinance as yf

from src.logger import get_logger
from src.paths import MARKET_DB_PATH, ensure_runtime_dirs


logger = get_logger()
DB_PATH = str(MARKET_DB_PATH)


def init_market_db() -> None:
    ensure_runtime_dirs()


def _table_name(ticker: str, interval: str) -> str:
    return (
        f"{ticker}_{interval}"
        .replace("=", "_")
        .replace("^", "_")
        .replace("-", "_")
    )


async def fetch_ticker_data_async(ticker: str, period: str = "2y", interval: str = "1h") -> pd.DataFrame:
    """
    Fetches OHLCV data with retry/backoff and an SQLite cache.
    Returns cached data when yfinance is unavailable.
    """
    init_market_db()
    table_name = _table_name(ticker, interval)

    conn = sqlite3.connect(DB_PATH)
    cached_df = pd.DataFrame()
    try:
        try:
            cached_df = pd.read_sql(
                f"SELECT * FROM {table_name}",
                conn,
                index_col="Date",
                parse_dates=["Date"],
            )
        except Exception:
            cached_df = pd.DataFrame()

        fetch_period = period
        if not cached_df.empty and len(cached_df) > 50:
            last_date = cached_df.index.max()
            gap_days = max((pd.Timestamp.now() - last_date).days, 0)
            if gap_days <= 1:
                fetch_period = "2d"
            elif gap_days <= 5:
                fetch_period = "5d"
            elif gap_days <= 30:
                fetch_period = "1mo"
            elif gap_days <= 90:
                fetch_period = "3mo"
            elif gap_days <= 365:
                fetch_period = "1y"

        for attempt in range(3):
            try:
                df = await asyncio.to_thread(
                    yf.download,
                    tickers=ticker,
                    period=fetch_period,
                    interval=interval,
                    progress=False,
                    auto_adjust=True,
                )
                if df.empty:
                    sleep_time = 2 ** attempt
                    logger.warning(
                        "No data returned for %s/%s (attempt %s). Retrying in %ss",
                        ticker,
                        interval,
                        attempt + 1,
                        sleep_time,
                    )
                    await asyncio.sleep(sleep_time)
                    continue

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)

                df = df.ffill().dropna()
                if hasattr(df.index, "tz_localize"):
                    df.index = df.index.tz_localize(None)
                df.index.name = "Date"

                if cached_df.empty:
                    df.to_sql(table_name, conn, if_exists="replace")
                    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(Date)")
                    return df

                last_cached_date = cached_df.index.max()
                new_rows = df[df.index > last_cached_date]
                if new_rows.empty:
                    return cached_df

                new_rows.to_sql(table_name, conn, if_exists="append")
                return pd.concat([cached_df, new_rows]).sort_index()

            except Exception as exc:
                sleep_time = 2 ** attempt
                logger.warning(
                    "Error fetching %s/%s (attempt %s): %s. Retrying in %ss",
                    ticker,
                    interval,
                    attempt + 1,
                    exc,
                    sleep_time,
                )
                await asyncio.sleep(sleep_time)

        logger.error("Failed to fetch data for %s/%s after 3 attempts.", ticker, interval)
        return cached_df
    finally:
        conn.close()


async def get_mtf_data(ticker: str) -> dict[str, pd.DataFrame]:
    ltf_task = fetch_ticker_data_async(ticker, period="730d", interval="1h")
    htf_task = fetch_ticker_data_async(ticker, period="max", interval="1d")
    ltf_df, htf_df = await asyncio.gather(ltf_task, htf_task)
    return {"ltf": ltf_df, "htf": htf_df}


def fetch_macro_data() -> dict:
    fallback = {
        "VIX": 0.0,
        "DXY": 0.0,
        "US10Y": 0.0,
        "DXY_EMA_50": 0.0,
        "US10Y_EMA_50": 0.0,
        "Regime": "Risk-On",
    }
    try:
        tickers = ["^VIX", "DX-Y.NYB", "^TNX"]
        df = yf.download(tickers, period="2y", interval="1d", progress=False, auto_adjust=True)
        if df.empty:
            return fallback

        df_close = df["Close"] if isinstance(df.columns, pd.MultiIndex) else df
        df_close = df_close.ffill().dropna(how="all")
        if df_close.empty:
            return fallback

        vix_val = float(df_close["^VIX"].iloc[-1])
        dxy_val = float(df_close["DX-Y.NYB"].iloc[-1])
        us10y_val = float(df_close["^TNX"].iloc[-1])
        dxy_ema_val = float(df_close["DX-Y.NYB"].ewm(span=50, adjust=False).mean().iloc[-1])
        us10y_ema_val = float(df_close["^TNX"].ewm(span=50, adjust=False).mean().iloc[-1])

        regime = "Risk-Off" if dxy_val > dxy_ema_val and us10y_val > us10y_ema_val else "Risk-On"
        return {
            "VIX": vix_val,
            "DXY": dxy_val,
            "US10Y": us10y_val,
            "DXY_EMA_50": dxy_ema_val,
            "US10Y_EMA_50": us10y_ema_val,
            "Regime": regime,
        }
    except Exception as exc:
        logger.error("Error fetching macro data: %s", exc)
        return fallback
