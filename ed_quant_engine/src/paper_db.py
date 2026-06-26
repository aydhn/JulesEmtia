from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import INITIAL_BALANCE
from src.logger import get_logger
from src.paths import ARCHIVE_DIR, PAPER_DB_PATH, REPO_ROOT, ensure_runtime_dirs


logger = get_logger()
SCHEMA_VERSION = 2
DB_PATH = str(PAPER_DB_PATH)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _connect():
    ensure_runtime_dirs()
    conn = sqlite3.connect(PAPER_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {row[1] for row in rows}
    except sqlite3.Error:
        return set()


def _schema_is_current(conn: sqlite3.Connection) -> bool:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    trade_cols = _table_columns(conn, "trades")
    required = {
        "trade_id",
        "ticker",
        "direction",
        "entry_time",
        "entry_price",
        "sl_price",
        "tp_price",
        "position_size",
        "status",
        "exit_time",
        "exit_price",
        "pnl",
        "pnl_pct",
        "risk_pct",
        "risk_amount",
        "open_risk",
        "is_breakeven",
        "partial_taken",
        "strategy_tag",
        "exit_reason",
        "metadata_json",
    }
    return version == SCHEMA_VERSION and required.issubset(trade_cols)


def archive_existing_db(reason: str = "schema_reset") -> Path | None:
    """Moves the active paper DB to archive and returns the archive path."""
    if not PAPER_DB_PATH.exists():
        return None

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = ARCHIVE_DIR / f"paper_db.{reason}.{stamp}.sqlite3"
    shutil.move(str(PAPER_DB_PATH), str(archive_path))
    logger.warning("Archived paper DB to %s", archive_path)
    return archive_path


def archive_legacy_paper_dbs(reason: str = "canonical_reset") -> list[str]:
    """Archives known legacy DB locations into ed_quant_engine/data/archive."""
    ensure_runtime_dirs()
    archived: list[str] = []
    candidates = [
        REPO_ROOT / "paper_db.sqlite3",
        REPO_ROOT / "data" / "paper_db.sqlite3",
        PAPER_DB_PATH,
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not candidate.exists():
            continue
        seen.add(resolved)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = ARCHIVE_DIR / f"{candidate.stem}.{reason}.{stamp}.sqlite3"
        shutil.copy2(candidate, target)
        archived.append(str(target))
    return archived


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_epochs (
            epoch_id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            reason TEXT NOT NULL,
            initial_balance REAL NOT NULL,
            archived_paths_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            balance REAL NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            direction TEXT NOT NULL CHECK(direction IN ('Long', 'Short')),
            entry_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            sl_price REAL NOT NULL,
            tp_price REAL NOT NULL,
            position_size REAL NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Open', 'Closed')),
            exit_time TEXT,
            exit_price REAL,
            pnl REAL NOT NULL DEFAULT 0,
            pnl_pct REAL NOT NULL DEFAULT 0,
            risk_pct REAL NOT NULL DEFAULT 0,
            risk_amount REAL NOT NULL DEFAULT 0,
            open_risk REAL NOT NULL DEFAULT 0,
            atr REAL NOT NULL DEFAULT 0,
            is_breakeven INTEGER NOT NULL DEFAULT 0,
            partial_taken INTEGER NOT NULL DEFAULT 0,
            strategy_tag TEXT NOT NULL DEFAULT 'unknown',
            exit_reason TEXT,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trades_ticker_status ON trades(ticker, status);

        CREATE TABLE IF NOT EXISTS trade_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER,
            event_time TEXT NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        """
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.execute(
        "INSERT OR IGNORE INTO portfolio(id, balance, updated_at) VALUES (1, ?, ?)",
        (INITIAL_BALANCE, _utc_now()),
    )


def record_account_epoch(
    reason: str,
    initial_balance: float = INITIAL_BALANCE,
    archived_paths: list[str] | None = None,
) -> int:
    with _connect() as conn:
        _create_schema(conn)
        cur = conn.execute(
            """
            INSERT INTO account_epochs(started_at, reason, initial_balance, archived_paths_json)
            VALUES (?, ?, ?, ?)
            """,
            (_utc_now(), reason, initial_balance, json.dumps(archived_paths or [])),
        )
        conn.execute(
            "UPDATE portfolio SET balance = ?, updated_at = ? WHERE id = 1",
            (initial_balance, _utc_now()),
        )
        return int(cur.lastrowid)


def init_db() -> None:
    ensure_runtime_dirs()
    if PAPER_DB_PATH.exists():
        with sqlite3.connect(PAPER_DB_PATH) as conn:
            if not _schema_is_current(conn):
                archive_existing_db("old_schema")

    with _connect() as conn:
        _create_schema(conn)
        epoch_count = conn.execute("SELECT COUNT(*) FROM account_epochs").fetchone()[0]
        if epoch_count == 0:
            conn.execute(
                """
                INSERT INTO account_epochs(started_at, reason, initial_balance, archived_paths_json)
                VALUES (?, 'initial_bootstrap', ?, '[]')
                """,
                (_utc_now(), INITIAL_BALANCE),
            )
    logger.info("Paper DB initialized at %s", PAPER_DB_PATH)


def archive_and_reset_account(reason: str = "manual_archive_reset") -> dict[str, Any]:
    archived = archive_legacy_paper_dbs(reason)
    if PAPER_DB_PATH.exists():
        PAPER_DB_PATH.unlink()
    init_db()
    epoch_id = record_account_epoch(reason=reason, archived_paths=archived)
    logger.warning("Paper account reset. epoch_id=%s archived=%s", epoch_id, archived)
    return {"epoch_id": epoch_id, "archived_paths": archived, "db_path": str(PAPER_DB_PATH)}


def _audit(conn: sqlite3.Connection, trade_id: int | None, event_type: str, payload: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO trade_audit(trade_id, event_time, event_type, payload_json)
        VALUES (?, ?, ?, ?)
        """,
        (trade_id, _utc_now(), event_type, json.dumps(payload, default=str)),
    )


def get_balance() -> float:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT balance FROM portfolio WHERE id = 1").fetchone()
        return float(row["balance"]) if row else INITIAL_BALANCE


def update_balance(new_balance: float) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE portfolio SET balance = ?, updated_at = ? WHERE id = 1",
            (float(new_balance), _utc_now()),
        )


def open_trade(
    ticker: str,
    direction: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    position_size: float,
    risk_pct: float = 0.0,
    atr: float = 0.0,
    strategy_tag: str = "confluence",
    metadata: dict[str, Any] | None = None,
) -> int:
    init_db()
    entry_price = float(entry_price)
    sl_price = float(sl_price)
    position_size = float(position_size)
    open_risk = abs(entry_price - sl_price) * position_size
    risk_amount = open_risk

    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades (
                ticker, direction, entry_time, entry_price, sl_price, tp_price,
                position_size, status, risk_pct, risk_amount, open_risk, atr,
                strategy_tag, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Open', ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                direction,
                _utc_now(),
                entry_price,
                sl_price,
                float(tp_price),
                position_size,
                float(risk_pct),
                risk_amount,
                open_risk,
                float(atr),
                strategy_tag,
                json.dumps(metadata or {}, default=str),
            ),
        )
        trade_id = int(cur.lastrowid)
        _audit(conn, trade_id, "OPEN", {"ticker": ticker, "direction": direction, "entry": entry_price})
    logger.info("Opened paper trade #%s %s %s @ %.6f", trade_id, direction, ticker, entry_price)
    return trade_id


def close_trade(trade_id: int, exit_price: float, exit_reason: str = "market") -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        trade = conn.execute(
            "SELECT * FROM trades WHERE trade_id = ? AND status = 'Open'",
            (trade_id,),
        ).fetchone()
        if not trade:
            return {}

        direction = trade["direction"]
        entry_price = float(trade["entry_price"])
        pos_size = float(trade["position_size"])
        exit_price = float(exit_price)

        if direction == "Long":
            pnl = (exit_price - entry_price) * pos_size
            pnl_pct = (exit_price - entry_price) / max(entry_price, 1e-12)
        else:
            pnl = (entry_price - exit_price) * pos_size
            pnl_pct = (entry_price - exit_price) / max(entry_price, 1e-12)

        conn.execute(
            """
            UPDATE trades
            SET status = 'Closed', exit_time = ?, exit_price = ?, pnl = ?,
                pnl_pct = ?, open_risk = 0, exit_reason = ?
            WHERE trade_id = ?
            """,
            (_utc_now(), exit_price, pnl, pnl_pct, exit_reason, trade_id),
        )
        balance = float(conn.execute("SELECT balance FROM portfolio WHERE id = 1").fetchone()["balance"])
        conn.execute(
            "UPDATE portfolio SET balance = ?, updated_at = ? WHERE id = 1",
            (balance + pnl, _utc_now()),
        )
        _audit(
            conn,
            trade_id,
            "CLOSE",
            {"exit": exit_price, "pnl": pnl, "pnl_pct": pnl_pct, "reason": exit_reason},
        )

    logger.info("Closed paper trade #%s @ %.6f | PnL %.2f", trade_id, exit_price, pnl)
    return {"trade_id": trade_id, "pnl": pnl, "pnl_pct": pnl_pct, "exit_price": exit_price}


def update_sl_price(trade_id: int, new_sl: float, is_breakeven: int = 0) -> None:
    init_db()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE trades
            SET sl_price = ?, is_breakeven = max(is_breakeven, ?)
            WHERE trade_id = ? AND status = 'Open'
            """,
            (float(new_sl), int(is_breakeven), trade_id),
        )
        _audit(conn, trade_id, "TRAILING_STOP", {"new_sl": float(new_sl), "is_breakeven": int(is_breakeven)})
    logger.info("Updated SL for trade #%s to %.6f", trade_id, new_sl)


def mark_partial_taken(trade_id: int) -> None:
    init_db()
    with _connect() as conn:
        conn.execute("UPDATE trades SET partial_taken = 1 WHERE trade_id = ?", (trade_id,))
        _audit(conn, trade_id, "PARTIAL_TAKEN", {})


def get_open_trades() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM trades WHERE status = 'Open' ORDER BY entry_time").fetchall()
        return [dict(row) for row in rows]


def get_closed_trades() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM trades WHERE status = 'Closed' ORDER BY exit_time", conn)


def audit_trade_history() -> dict[str, Any]:
    init_db()
    with _connect() as conn:
        open_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'Open'").fetchone()[0]
        closed_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status = 'Closed'").fetchone()[0]
        balance = conn.execute("SELECT balance FROM portfolio WHERE id = 1").fetchone()["balance"]
        realized = conn.execute("SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE status = 'Closed'").fetchone()[0]
        orphan_audit = conn.execute(
            """
            SELECT COUNT(*)
            FROM trade_audit a
            LEFT JOIN trades t ON a.trade_id = t.trade_id
            WHERE a.trade_id IS NOT NULL AND t.trade_id IS NULL
            """
        ).fetchone()[0]
        schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
    return {
        "db_path": str(PAPER_DB_PATH),
        "schema_version": int(schema_version),
        "open_trades": int(open_count),
        "closed_trades": int(closed_count),
        "balance": float(balance),
        "realized_pnl": float(realized),
        "orphan_audit_rows": int(orphan_audit),
        "ok": schema_version == SCHEMA_VERSION and orphan_audit == 0,
    }
