# ED Capital Quant Engine 🚀

A low-frequency, high-win-rate, zero-budget quantitative trading bot built purely in Python.

Designed for autonomous operations on Commodities and Forex (TRY-based) markets, strictly adhering to **JP Morgan Risk standards** and **Bill Benter statistical modeling**.

## Features
* **Zero Budget Ecosystem:** Built strictly using free APIs (`yfinance`), open-source libraries (`scikit-learn`, `pandas-ta`), and local execution (No AWS bills or Web scraping).
* **Multi-Timeframe Analysis (MTF):** Uses Daily (1D) data for master trend confirmation and Hourly (1H) data for sniper entries.
* **Risk of Ruin Prevention:** Implements dynamic ATR trailing stops, fractional Kelly Criterion position sizing, Pearson correlation limits, and VIX Circuit Breakers.
* **Machine Learning Validation:** Employs a local `RandomForestClassifier` trained on historical anomalies to veto low-probability technical signals.
* **NLP Sentiment Filters:** Parses free RSS feeds using NLTK VADER to confirm technical signals against current macro-economic news.
* **Realistic Execution Modeling:** Penalizes simulated results heavily with dynamic Bid/Ask spreads and Volatility-adjusted slippage.
* **Two-Way Telegram Command Center:** Complete remote control (Status, Pause, Resume, Panic Close, Force Scan) through Telegram bots asynchronously.
* **Institutional Reporting:** Generates ED Capital standard "Tear Sheets" with automated Monte Carlo stress-testing metrics.

## Setup & Deployment

1. **Configuration:**
   Rename `.env.example` to `.env` and fill in your Telegram Bot Token and Admin Chat ID.
   ```bash
   cp .env.example .env
   ```
2. **Docker Deployment:**
   Deploy securely using the provided Docker-Compose architecture. The `paper_db.sqlite3` and `rf_model.pkl` are mounted as persistent volumes to protect your transaction history and machine learning models from container reboots.
   ```bash
   chmod +x manage_bot.sh
   ./manage_bot.sh start
   ```

3. **Log Monitoring:**
   ```bash
   ./manage_bot.sh logs
   ```
