# ED Capital Quant Engine

A high-performance, low-frequency, zero-budget quantitative trading engine built in Python. Designed with the precision of a Senior Quant Developer, the risk management of a JP Morgan Fund Manager, and the ingenuity of Bill Benter.

## Features
- **Zero Budget Ecosystem:** Uses exclusively free libraries (`yfinance`, `pandas_ta`, `scikit-learn`, `nltk`).
- **Multi-Timeframe Analysis (MTF):** Filters entry signals (1H) against macro trends (1D) with strict zero lookahead bias checks using backward merging.
- **Dynamic Risk Management:** Fractional Kelly Criterion position sizing, ATR-based trailing stops, and volatility-adjusted slippage.
- **Circuit Breakers & Vetoes:**
  - VIX Flash Crash Protection
  - Dynamic Correlation Vetos
  - Natural Language Processing (NLP) Sentiment Vetoes via RSS Feeds
  - Random Forest ML Signal Validation
- **Solid Architecture:** Fully containerized via Docker, local SQLite state management, and an Abstract Base Broker interface for future live integration.
- **Two-Way Telegram Interface:** Real-time reporting, panic buttons, and autonomous heartbeat.

## Installation

1. Clone the repository.
2. Setup your environment:
   `cp .env.example .env` (Add your Telegram Token and Chat ID).
3. Start the bot via Docker Compose:
   `./manage_bot.sh start`

## Operations
Manage the bot using the included script:
- `./manage_bot.sh start`
- `./manage_bot.sh stop`
- `./manage_bot.sh logs`
- `./manage_bot.sh status`

## Disclaimer
This is for educational and paper-trading purposes only. Financial markets are extremely risky.
