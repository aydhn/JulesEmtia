from __future__ import annotations

import importlib
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = REPO_ROOT / "ed_quant_engine"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("HealthCheck")


def check_python_version() -> bool:
    required = (3, 10)
    current = sys.version_info
    if current < required:
        logger.error("Python %s.%s+ required. Found %s.%s", required[0], required[1], current.major, current.minor)
        return False
    logger.info("Python version: %s.%s.%s [OK]", current.major, current.minor, current.micro)
    return True


def check_dependencies() -> bool:
    required_packages = [
        "yfinance",
        "pandas",
        "pandas_ta",
        "sklearn",
        "telegram",
        "matplotlib",
        "feedparser",
        "gymnasium",
        "stable_baselines3",
        "rich",
        "dotenv",
        "joblib",
    ]
    missing = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)
    if missing:
        logger.error("Missing required packages: %s", ", ".join(missing))
        return False
    logger.info("Core dependencies are importable [OK]")
    return True


def check_env_vars() -> bool:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        logger.error(".env file is missing.")
        return False
    content = env_path.read_text(encoding="utf-8")
    env_values = {}
    for line in content.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            env_values[key.strip()] = value.strip().strip("\"'")

    token = env_values.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = env_values.get("ADMIN_CHAT_ID") or env_values.get("TELEGRAM_CHAT_ID", "")
    placeholders = {"test", "dummy", "placeholder", "changeme", "none"}
    if "TELEGRAM_BOT_TOKEN=" not in content:
        logger.warning("TELEGRAM_BOT_TOKEN not found in .env. Telegram notifications disabled.")
    if "ADMIN_CHAT_ID=" not in content and "TELEGRAM_CHAT_ID=" not in content:
        logger.warning("ADMIN_CHAT_ID not found in .env. Telegram sending will be disabled.")
    if token.lower() in placeholders or token.lower().startswith("your_"):
        logger.warning("TELEGRAM_BOT_TOKEN looks like a placeholder. Telegram notifications disabled.")
    if chat_id.lower() in placeholders or chat_id.lower().startswith("your_"):
        logger.warning("ADMIN_CHAT_ID looks like a placeholder. Telegram notifications disabled.")
    logger.info(".env file checks passed [OK]")
    return True


def check_directories() -> bool:
    for directory in ("logs", "data", "reports", "models"):
        path = ENGINE_ROOT / directory
        path.mkdir(parents=True, exist_ok=True)
        if not os.access(path, os.W_OK):
            logger.error("Directory is not writable: %s", path)
            return False
    logger.info("Runtime directories exist and are writable [OK]")
    return True


def check_engine_imports() -> bool:
    sys.path.insert(0, str(ENGINE_ROOT))
    try:
        import src.paper_db as db
        from src.paths import MARKET_DB_PATH, PAPER_DB_PATH

        db.init_db()
        audit = db.audit_trade_history()
        logger.info("Paper DB audit [OK]: %s", audit)
        logger.info("Canonical paper DB: %s", PAPER_DB_PATH)
        logger.info("Canonical market DB: %s", MARKET_DB_PATH)
        return bool(audit.get("ok"))
    except Exception as exc:
        logger.error("Engine import/schema check failed: %s", exc)
        return False


def check_network() -> bool:
    try:
        with urllib.request.urlopen("https://query2.finance.yahoo.com/v8/finance/chart/%5EVIX", timeout=8) as response:
            status = response.status
        if status in (200, 404, 429):
            level = logger.info if status != 429 else logger.warning
            level("Yahoo Finance network check returned HTTP %s [OK/degraded]", status)
            return True
        logger.warning("Yahoo Finance network check returned unexpected HTTP %s", status)
        return True
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 429):
            logger.warning("Yahoo Finance network check returned HTTP %s [degraded but reachable]", exc.code)
            return True
        logger.error("Network check failed with HTTP %s", exc.code)
        return False
    except Exception as exc:
        logger.error("Network check failed: %s", exc)
        return False


if __name__ == "__main__":
    logger.info("--- Starting Windows Health Check ---")
    checks = [
        check_python_version(),
        check_dependencies(),
        check_env_vars(),
        check_directories(),
        check_engine_imports(),
        check_network(),
    ]
    if all(checks):
        logger.info("All health checks passed. System is ready.")
        sys.exit(0)
    logger.error("Health checks failed. Fix the errors before starting the bot.")
    sys.exit(1)
