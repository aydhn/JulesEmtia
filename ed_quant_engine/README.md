# ED Capital Quant Engine

A high-win-rate, low-frequency, and robust algorithmic trading engine designed with strict risk management parameters and complete multi-timeframe confirmation. Inspired by institutional practices and run entirely on open-source, zero-budget infrastructure.

## Key Features

- **Multi-Timeframe Confluence (MTF):** Strict alignment between Daily (Macro) and Hourly (Micro) trends, fully protecting against lookahead bias.
- **Dynamic Risk Management:** Fractional Kelly sizing with ATR-adjusted stop losses and aggressive trailing stops.
- **Circuit Breakers & Macro Filters:** Integrates VIX anomaly checks, DXY & Yield trend vetoes, and sudden Z-Score flash-crash pauses.
- **Machine Learning Validator:** A local `RandomForestClassifier` prevents low-probability technical setups from executing.
- **NLP Sentiment Filter:** Integrates RSS-based `nltk.vader` logic to check news sentiment against the technical direction.
- **Execution Modeling:** Factoring realistic spread and dynamic ATR-driven slippage costs directly into the PnL.
- **Two-Way Telegram Interface:** Fully controllable from Telegram via secure chat ID whitelisting (`/durum`, `/durdur`, `/kapat_hepsi`).
- **Institutional Reporting:** Weekly PDF/Image Tear Sheets summarizing Win Rate, Drawdown, Profit Factor, and Risk of Ruin via Monte Carlo Simulation.

## Architecture & DevOps

- **Broker Abstraction Layer:** SQLite base class (`PaperBroker`) ready to be hot-swapped for Live API Execution (Binance, IBKR).
- **Dockerized & Persistent:** Managed effortlessly through `docker-compose` guaranteeing SQLite history, logs, and trained `.pkl` models survive restarts.

## Setup Instructions

### 1. Requirements

Ensure `docker` and `docker-compose` are installed.

### 2. Configuration

```bash
git clone <repo>
cd ed_quant_engine
cp .env.example .env
```
Edit the `.env` file to insert your specific `TELEGRAM_BOT_TOKEN` and `ADMIN_CHAT_ID`.

### 3. Deploy

```bash
./scripts/manage_bot.sh deploy
```

Watch logs:
```bash
./scripts/manage_bot.sh logs
```

## Disclaimer
This project simulates institutional strategies for educational and paper trading purposes.

