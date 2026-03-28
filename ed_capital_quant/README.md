# ED Capital Quant Engine 🚀

A low-frequency, high-win-rate, zero-budget, multi-timeframe quantitative trading engine designed for Commodities and Forex (TRY pairs).

## Features
- **Zero Budget**: Powered by `yfinance`, `pandas_ta`, `sqlite3`, and local ML libraries.
- **Robustness**: Fault-tolerant asynchronous event loop, state recovery via SQLite, dynamic logging.
- **Confluence Strategy**: Trend (EMA), Momentum (RSI, MACD), Volatility (ATR, Bollinger Bands).
- **Risk Management**: ATR-based dynamic stop-loss, Take-Profit, and trailing stops.
- **Machine Learning Filter**: Random Forest Classifier to veto low-probability signals (Phase 18).
- **Macro Regime Filter**: Integrates DXY, US10Y, and VIX to prevent trend-fighting (Phase 6, 19).
- **Dockerized**: Easy deployment via `docker-compose`.

## Installation
1. Clone the repository.
2. Setup the `.env` file based on `.env.template` (Telegram Bot Token required).
3. Run `docker-compose up -d --build` or execute locally via `python main.py`.

## Directory Structure
- `core/`: Configurations, Logging, Database, Telegram Notifier, Data Loader.
- `features/`: Technical indicators and Feature Engineering.
- `strategy/`: Core algorithmic logic and Confluence testing.
- `risk/`: Position Sizing, Kelly Criterion, Correlation Matrix.
- `execution/`: Broker Abstraction, Slippage Modeling.
- `analytics/`: Backtesting, Walk-Forward Optimization, Tear Sheet Generation.

> "Discipline, Risk Management, and Mathematical Expectation."
