# ED Capital Quant Engine

A high-frequency, autonomous algorithmic trading engine designed with strict quantitative finance principles. Built to operate continuously in a Dockerized environment, the engine utilizes multi-timeframe analysis, dynamic risk management, machine learning validation, and natural language processing for sentiment analysis.

## Features

- **Multi-Timeframe Confluence**: Synchronizes Daily (HTF) and Hourly (LTF) data strictly preventing lookahead bias.
- **Dynamic Risk Management**: Incorporates Fractional Kelly Criterion and ATR-based Trailing Stops.
- **Circuit Breakers**: Monitors VIX and calculates Z-Scores to halt trading during Black Swan events or Flash Crashes.
- **Machine Learning Validation**: Validates technical signals using a dynamically re-trained Random Forest Classifier.
- **NLP Sentiment Filtering**: Aggregates news using NLTK VADER to veto technical signals conflicting with market sentiment.
- **Correlation Veto**: Prevents risk duplication across highly correlated assets.
- **Telegram Orchestration**: Fully controlled via Telegram with commands (`/durum`, `/durdur`, `/devam`, `/kapat_hepsi`, `/tara`).

## Prerequisites

- Docker and Docker Compose
- A Telegram Bot Token and Chat ID

## Setup

1. **Clone the repository**
2. **Configure Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID
   ```
3. **Start the Engine**
   ```bash
   ./manage_bot.sh start
   ```

## Operations

- **Start**: `./manage_bot.sh start`
- **Stop**: `./manage_bot.sh stop`
- **Restart**: `./manage_bot.sh restart`
- **Logs**: `./manage_bot.sh logs`
- **Status**: `./manage_bot.sh status`

## Architecture

The system is modularized into several domains:
- `src/core`: Configuration, Logging, and SQLite database setup.
- `src/data`: Asynchronous data fetching via Yahoo Finance and technical indicator processing.
- `src/filters`: Macroeconomic (VIX, DXY, TNX), Machine Learning (Random Forest), and NLP sentiment logic.
- `src/strategy`: Dynamic portfolio sizing (Kelly), execution costing (slippage/spread), and MTF rule evaluations.
- `src/execution`: Abstract Broker layer supporting paper trading and live connections.
- `src/bot`: The main orchestration loop and Telegram bot interface.

## Reporting

The engine auto-generates a weekly HTML Tear Sheet and sends it via Telegram, evaluating metrics such as Net PnL, Win Rate, Profit Factor, Max Drawdown, and Monte Carlo Risk of Ruin.
