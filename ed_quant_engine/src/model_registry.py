"""model_registry.py — Persistent ML model performance tracking.

Every training cycle appends a record for each ticker.  The registry
detects statistical model degradation by comparing the most recent
rolling-average OOS accuracy against a running historical baseline and
triggers a re-bootstrap flag when degradation exceeds the threshold.

Schema (SQLite, ``model_performance`` table):
    id            INTEGER PRIMARY KEY
    ticker        TEXT
    model_type    TEXT  (RF | PPO)
    cycle         INTEGER
    trained_at    TEXT  (ISO-8601 UTC)
    oos_accuracy  REAL  (for RF: OOS accuracy %; for PPO: win rate %)
    samples       INTEGER
    notes         TEXT
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.logger import get_logger
from src.paths import DATA_DIR, ensure_runtime_dirs

logger = get_logger()

REGISTRY_DB_PATH = DATA_DIR / "model_registry.sqlite3"
# If the rolling mean drops more than this fraction below the historical
# mean, trigger a re-bootstrap.
DEGRADATION_THRESHOLD = 0.05   # 5 percentage points

# Minimum cycles before degradation detection is meaningful.
MIN_HISTORY_CYCLES = 5


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def _connect():
    ensure_runtime_dirs()
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _init_registry() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS model_performance (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker       TEXT NOT NULL,
                model_type   TEXT NOT NULL CHECK(model_type IN ('RF', 'PPO')),
                cycle        INTEGER NOT NULL,
                trained_at   TEXT NOT NULL,
                oos_accuracy REAL NOT NULL,
                samples      INTEGER NOT NULL DEFAULT 0,
                notes        TEXT NOT NULL DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_mp_ticker ON model_performance(ticker, model_type);
            CREATE INDEX IF NOT EXISTS idx_mp_cycle  ON model_performance(ticker, model_type, cycle);
            """
        )


# Ensure schema exists at import time.
try:
    _init_registry()
except Exception as _exc:
    logger.warning("Model registry init failed (non-fatal): %s", _exc)


def record_training(
    ticker: str,
    model_type: str,
    cycle: int,
    oos_accuracy: float,
    samples: int = 0,
    notes: dict[str, Any] | None = None,
) -> int:
    """Append one training record and return its row id."""
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO model_performance
                (ticker, model_type, cycle, trained_at, oos_accuracy, samples, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                model_type,
                cycle,
                _utc_now(),
                float(oos_accuracy),
                int(samples),
                json.dumps(notes or {}),
            ),
        )
        return int(cur.lastrowid)


def get_history(ticker: str, model_type: str, last_n: int = 20) -> list[dict[str, Any]]:
    """Return the most recent *last_n* training records for a ticker/model pair."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM model_performance
            WHERE ticker = ? AND model_type = ?
            ORDER BY cycle DESC
            LIMIT ?
            """,
            (ticker, model_type, last_n),
        ).fetchall()
        return [dict(r) for r in rows]


def is_degraded(ticker: str, model_type: str, rolling_window: int = 3) -> bool:
    """Return True when the model shows statistically significant degradation.

    Degradation = rolling mean of last *rolling_window* cycles drops more than
    DEGRADATION_THRESHOLD below the historical mean of the preceding cycles.
    Only evaluated when at least MIN_HISTORY_CYCLES records exist.
    """
    history = get_history(ticker, model_type, last_n=MIN_HISTORY_CYCLES + rolling_window)
    if len(history) < MIN_HISTORY_CYCLES:
        return False

    accuracies = [r["oos_accuracy"] for r in history]
    recent = accuracies[:rolling_window]
    baseline = accuracies[rolling_window:]

    if not baseline:
        return False

    recent_mean = sum(recent) / len(recent)
    baseline_mean = sum(baseline) / len(baseline)

    degraded = (baseline_mean - recent_mean) > DEGRADATION_THRESHOLD * 100
    if degraded:
        logger.warning(
            "Model degradation detected: %s/%s recent_avg=%.1f%% baseline_avg=%.1f%%",
            ticker,
            model_type,
            recent_mean,
            baseline_mean,
        )
    return degraded


def degradation_summary() -> dict[str, list[str]]:
    """Return a dict mapping model_type to list of degraded tickers."""
    from src.config import ALL_TICKERS

    result: dict[str, list[str]] = {"RF": [], "PPO": []}
    for model_type in ("RF", "PPO"):
        for ticker in ALL_TICKERS:
            if is_degraded(ticker, model_type):
                result[model_type].append(ticker)
    return result


def registry_stats() -> dict[str, Any]:
    """High-level summary of the registry for heartbeat reports."""
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM model_performance").fetchone()[0]
        tickers = conn.execute("SELECT COUNT(DISTINCT ticker) FROM model_performance").fetchone()[0]
        latest = conn.execute(
            "SELECT MAX(trained_at) FROM model_performance"
        ).fetchone()[0]
    return {
        "registry_db": str(REGISTRY_DB_PATH),
        "total_records": int(total),
        "distinct_tickers": int(tickers),
        "latest_training": latest,
    }
