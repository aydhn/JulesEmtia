from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime

import pandas as pd
import yfinance as yf
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskID, TextColumn, TimeElapsedColumn
from rich.table import Table

from src.config import INGEST_CONCURRENCY
from src.logger import get_logger
from src.paths import MARKET_DB_PATH, ensure_runtime_dirs


logger = get_logger()
console = Console()
DB_PATH = str(MARKET_DB_PATH)

INTERVALS = {
    "1d": "max",
    "1h": "730d",
}


def _table_name(ticker: str, interval: str) -> str:
    return (
        f"{ticker}_{interval}"
        .replace("=", "_")
        .replace("^", "_")
        .replace("-", "_")
    )


def _get_row_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])
    except Exception:
        return 0


def _upsert_df(conn: sqlite3.Connection, df: pd.DataFrame, table: str) -> int:
    if df.empty:
        return 0

    existing_count = _get_row_count(conn, table)
    if existing_count > 0:
        try:
            last_date = conn.execute(f"SELECT MAX(Date) FROM {table}").fetchone()[0]
            new_rows = df[df.index > pd.Timestamp(last_date)]
            if new_rows.empty:
                return 0
            new_rows.to_sql(table, conn, if_exists="append")
            return len(new_rows)
        except Exception as exc:
            logger.warning("Upsert fallback for %s: %s", table, exc)

    df.to_sql(table, conn, if_exists="replace")
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_date ON {table}(Date)")
    return len(df)


async def _fetch_one(
    ticker: str,
    interval: str,
    period: str,
    progress: Progress,
    task_id: TaskID,
) -> tuple[str, str, int]:
    label = f"{ticker} ({interval})"
    progress.update(task_id, description=f"[cyan]Fetching: {label}")

    for attempt in range(3):
        try:
            df = await asyncio.to_thread(
                yf.download,
                tickers=ticker,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                sleep_t = 2 ** attempt
                logger.warning("No data for %s/%s attempt %s. Retry in %ss", ticker, interval, attempt + 1, sleep_t)
                await asyncio.sleep(sleep_t)
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df = df.ffill().dropna()
            if hasattr(df.index, "tz_localize"):
                df.index = df.index.tz_localize(None)
            df.index.name = "Date"

            with sqlite3.connect(DB_PATH) as conn:
                table = _table_name(ticker, interval)
                new_rows = _upsert_df(conn, df, table)
                total_rows = _get_row_count(conn, table)

            progress.update(
                task_id,
                advance=1,
                description=f"[green]OK {label} ({total_rows:,} rows, +{new_rows})",
            )
            return ticker, interval, total_rows

        except Exception as exc:
            logger.error("Error fetching %s/%s attempt %s: %s", ticker, interval, attempt + 1, exc)
            await asyncio.sleep(2 ** attempt)

    progress.update(task_id, advance=1, description=f"[red]ERR {label}")
    return ticker, interval, 0


async def run_bulk_ingest(tickers: list[str]) -> dict[str, dict[str, int]]:
    ensure_runtime_dirs()
    total_tasks = len(tickers) * len(INTERVALS)
    results: dict[str, dict[str, int]] = {ticker: {} for ticker in tickers}
    semaphore = asyncio.Semaphore(max(1, INGEST_CONCURRENCY))

    try:
        console.print(
            f"\n[bold cyan]Bulk data ingest starting "
            f"({len(tickers)} tickers x {len(INTERVALS)} intervals = {total_tasks} tasks)[/bold cyan]\n"
        )
    except Exception:
        pass

    async def guarded_fetch(ticker: str, interval: str, period: str, progress: Progress, task_id: TaskID):
        async with semaphore:
            return await _fetch_one(ticker, interval, period, progress, task_id)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Starting...", total=total_tasks)
        coros = []
        for interval, period in INTERVALS.items():
            for ticker in tickers:
                coros.append(guarded_fetch(ticker, interval, period, progress, task_id))
                await asyncio.sleep(0.05)
        fetch_results = await asyncio.gather(*coros, return_exceptions=True)

    for res in fetch_results:
        if isinstance(res, Exception):
            logger.warning("Bulk ingest task failed: %s", res)
            continue
        ticker, interval, row_count = res
        results[ticker][interval] = row_count

    table = Table(title="Market warehouse ingest summary", show_lines=True)
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Daily rows", justify="right", style="green")
    table.add_column("Hourly rows", justify="right", style="blue")
    table.add_column("Status", justify="center")

    for ticker in tickers:
        rows_1d = results[ticker].get("1d", 0)
        rows_1h = results[ticker].get("1h", 0)
        ok = rows_1d >= 200 and rows_1h >= 200
        table.add_row(ticker, f"{rows_1d:,}", f"{rows_1h:,}", "OK" if ok else "SPARSE")

    try:
        console.print(table)
    except Exception:
        pass

    good = sum(1 for ticker in tickers if results[ticker].get("1d", 0) >= 200 and results[ticker].get("1h", 0) >= 200)
    logger.info("Bulk ingest complete. sufficient=%s/%s db=%s", good, len(tickers), DB_PATH)

    try:
        from src.notifier import send_telegram_message

        await send_telegram_message(
            "<b>Market warehouse update</b>\n"
            f"Symbols: {len(tickers)}\n"
            f"Sufficient data: {good}/{len(tickers)}\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
    except Exception:
        pass
    return results
