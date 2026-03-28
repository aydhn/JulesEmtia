# ED Capital Quant Engine 🚀

A low-frequency, high-win-rate, zero-budget, multi-timeframe quantitative trading engine designed for Commodities and Forex (TRY pairs).

## Features
- **Zero Budget**: Powered by `yfinance`, `pandas_ta`, `sqlite3`, and local ML libraries.
- **Robustness**: Fault-tolerant asynchronous event loop, state recovery via SQLite, dynamic logging.
- **Confluence Strategy**: Trend (EMA), Momentum (RSI, MACD), Volatility (ATR, Bollinger Bands).
- **Risk Management**: ATR-based dynamic stop-loss, Take-Profit, Kelly Criterion, and trailing stops.
- **Machine Learning Filter**: Random Forest Classifier to veto low-probability signals (Phase 18).
- **Macro Regime Filter**: Integrates DXY, US10Y, and VIX to prevent trend-fighting (Phase 6, 19).
- **Execution & Slippage**: Broker abstraction layer, volatile slippage, and dynamic spread simulation (Phase 21, 24).
- **Analytics & Reporting**: Walk-Forward Optimization, Monte Carlo Risk of Ruin, and Tear Sheets (Phase 13, 14, 22).
- **Dockerized & Systemd**: Easy deployment via `docker-compose` or `systemctl`.

## Architecture Highlights
- `core/`: Configurations, Logging, Database, Telegram Notifier, Machine Learning Validator.
- `data/`: Multi-timeframe OHLCV Loader, Macro Indicators, News Sentiment (NLTK VADER).
- `features/`: Technical indicators and Feature Engineering.
- `strategy/`: Core algorithmic logic and Confluence testing.
- `risk/`: Position Sizing, Kelly Criterion, Correlation Matrix.
- `execution/`: Broker Abstraction (PaperBroker), Spread/Slippage Modeling.
- `analytics/`: Backtesting, Walk-Forward Optimization, Tear Sheet Generation, Monte Carlo.

## Installation & Deployment

### Virtual Environment (Local)
1. `python3 -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`

### Docker (Recommended)
```bash
chmod +x deploy.sh
./deploy.sh
```

### Systemd (Linux Background Daemon)
```bash
chmod +x manage_bot.sh
sudo cp systemd/quant_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable quant_bot
./manage_bot.sh start
```

### Security
Ensure you configure the `.env` file before starting the engine. NEVER commit your `.env` file or SQLite database.
```
TELEGRAM_BOT_TOKEN=your_token
ADMIN_CHAT_ID=your_id
TZ=Europe/Istanbul
```

> "Discipline, Risk Management, and Mathematical Expectation."
