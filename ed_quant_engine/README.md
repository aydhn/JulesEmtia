# ED Capital Quant Engine

A professional, zero-budget, multi-timeframe quantitative trading engine built in Python. Designed for high win-rate strategies across Commodities and TRY-based Forex pairs.

## Architecture & Features
- **Zero-Budget Data:** Uses `yfinance` exclusively. No paid APIs or scraping tools.
- **Multi-Timeframe Confluence (MTF):** Aligns HTF (Daily) trends with LTF (Hourly) entry triggers without Lookahead Bias (`pd.merge_asof(direction='backward')`).
- **Dynamic Risk Management:** Features ATR-based trailing stops, fractional Kelly Criterion position sizing, and correlation vetoes to prevent risk duplication.
- **Black Swan Protection:** Integrates a VIX circuit breaker and Z-Score anomaly detection to halt trading during flash crashes.
- **Machine Learning Validation:** Employs a local `RandomForestClassifier` via `scikit-learn` to filter out low-probability technical signals based on historical patterns.
- **NLP Sentiment Veto:** Uses `feedparser` and `NLTK VADER` to read RSS news headlines, vetoing technical signals that directly contradict macroeconomic sentiment.
- **Realistic Execution:** Simulates slippage and spreads dynamically based on current volatility to ensure paper trade PnL reflects reality.
- **Robustness Testing:** Includes a vectorized backtester, Walk-Forward Optimization (WFO), and a Monte Carlo engine measuring the "Risk of Ruin".
- **Institutional Reporting:** Automatically generates PDF/HTML Tearsheets benchmarking performance against inflation and USD/TRY holding returns.
- **Two-Way Telegram Commands:** Supports commands like `/durum`, `/durdur`, `/devam`, `/kapat_hepsi`, `/tara` for manual overrides.

## Setup Instructions

1. **Clone & Env:**
   Copy `.env.example` to `.env` and configure your Telegram credentials (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_ADMIN_CHAT_ID`).

2. **Docker Deployment (Recommended):**
   The entire system is containerized with proper volume mapping to preserve SQLite states (`paper_db.sqlite3`), ML models, and logs.

   ```bash
   chmod +x manage_bot.sh
   ./manage_bot.sh start
   ```

3. **Manual Execution (Virtual Environment):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python main.py
   ```

## Operations
- All alerts, performance summaries, and trade executions are communicated exclusively via Telegram.
- Background execution is managed by Docker or the provided `quant_bot.service` systemd unit file.
