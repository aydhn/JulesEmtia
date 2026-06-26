from __future__ import annotations

from pathlib import Path


ENGINE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ENGINE_ROOT.parent

DATA_DIR = ENGINE_ROOT / "data"
LOG_DIR = ENGINE_ROOT / "logs"
MODEL_DIR = ENGINE_ROOT / "models"
REPORT_DIR = ENGINE_ROOT / "reports"
ARCHIVE_DIR = DATA_DIR / "archive"
MODEL_QUARANTINE_DIR = MODEL_DIR / "quarantine"

MARKET_DB_PATH = DATA_DIR / "market_data.sqlite3"
PAPER_DB_PATH = DATA_DIR / "paper_db.sqlite3"
LOG_PATH = LOG_DIR / "quant_engine.log"
ENV_PATH = REPO_ROOT / ".env"


def ensure_runtime_dirs() -> None:
    for path in (DATA_DIR, LOG_DIR, MODEL_DIR, REPORT_DIR, ARCHIVE_DIR, MODEL_QUARANTINE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def sanitize_ticker(ticker: str) -> str:
    return (
        ticker.replace("=", "_")
        .replace("^", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
    )


def model_file(ticker: str, suffix: str) -> Path:
    return MODEL_DIR / f"{sanitize_ticker(ticker)}_{suffix}"


def quarantine_file(original: Path, reason: str) -> Path:
    MODEL_QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    safe_reason = reason.replace(" ", "_").replace("/", "_")
    return MODEL_QUARANTINE_DIR / f"{original.stem}.{safe_reason}{original.suffix}"
