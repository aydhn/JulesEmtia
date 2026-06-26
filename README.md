# JulesEmtia / ED Capital Quant Engine

Low-frequency paper trading and continuous-learning bot for commodities and TRY FX pairs. The runtime is local, zero-budget, no-scraping, and Telegram-first. No real orders are sent.

## Current Runtime

- Canonical app root: `ed_quant_engine`
- Windows entrypoint: `start_windows.bat`
- Main orchestrator: `ed_quant_engine/main.py`
- Runtime data: `ed_quant_engine/data`
- Logs: `ed_quant_engine/logs/quant_engine.log`
- Models: `ed_quant_engine/models`
- Reports: `ed_quant_engine/reports`

## What It Does

- Uses yfinance for 1h/1d OHLCV and macro proxies: VIX, DXY, US10Y.
- Builds MTF features with lookahead protection: hourly signals only see shifted, closed daily context.
- Computes EMA, RSI, MACD, ATR, Bollinger, ADX, StochRSI, MFI, CMF, Supertrend, Keltner, Donchian, VWAP proxy, volatility regime and divergence features.
- Paper trades through SQLite with schema versioning, account epochs, trade audit, ATR SL/TP, breakeven and trailing stop.
- Applies macro, sentiment, ML, correlation, max-position and total-risk vetoes.
- Trains per-symbol RF and PPO models with manifest files; stale or mismatched models are quarantined.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r ed_quant_engine\requirements.txt
copy .env.template .env
python scripts\windows_healthcheck.py
```

Edit `.env` locally:

```env
TELEGRAM_BOT_TOKEN=
ADMIN_CHAT_ID=
ENVIRONMENT=production
TZ=Europe/Istanbul
```

Start on Windows:

```powershell
.\start_windows.bat
```

Validation helpers:

```powershell
python scripts\runtime_diagnostics.py
python scripts\archive_reset_paper_account.py
```

## Operating Rules

- Keep `master == origin/master` at handoff.
- Do not commit `.env`, SQLite DBs, logs, reports or generated models.
- Treat Yahoo Finance `429` as degraded connectivity if cache exists; do not crash the bot.
- Telegram credentials are optional for offline operation, but required for live notifications.
