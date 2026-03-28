# ED Capital Quant Engine

## Overview
A low-frequency, high-win-rate, modular quantitative trading engine built in Python. Designed with a strict zero-budget philosophy, relying entirely on open-source libraries and free data providers.

## Architecture & Features
* **Zero Cost Infrastructure:** Data via `yfinance`, technicals via `pandas_ta`, and reporting via `matplotlib`.
* **Multi-Timeframe Confluence (MTF):** Strict daily trend alignment before hourly execution. Zero lookahead bias.
* **Macro Regime Filtering:** VIX circuit breakers, DXY/TNX headwinds veto, and Z-Score flash crash detection.
* **Risk Management:** Dynamic ATR-based trailing stops, Fractional Kelly Criterion position sizing, and correlation duplication vetos.
* **Machine Learning Validation:** Random Forest Classifier to filter historically low-probability technical setups.
* **Fundamental Analysis:** NLTK VADER sentiment analysis on RSS news feeds.
* **Execution Realism:** Dynamic spread and ATR-adjusted slippage modeling.
* **Reporting:** Tear sheet generation with Monte Carlo Risk of Ruin simulations.

## Quick Start
1. Copy `.env.example` to `.env` and configure your Telegram token and Chat ID.
2. Ensure Docker and Docker Compose are installed.
3. Run `./manage_bot.sh deploy` to build and start the engine in detached mode.
