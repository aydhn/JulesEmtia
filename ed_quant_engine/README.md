# ED Capital Quant Engine 🚀

A low-frequency, highly robust, multi-timeframe algorithmic trading bot designed with a "zero-budget" constraint using free APIs (yfinance) and open-source libraries.

## 🏗️ Architecture & Purpose

Designed with the risk tolerance of JP Morgan and the algorithmic intuition of Bill Benter.
- **Low Frequency:** Targets hourly entries (1H) validated by daily trends (1D) to minimize noise and maximize the win rate.
- **Zero Lookahead Bias:** Timeframe alignment is strictly backward-shifted.
- **Circuit Breakers:** VIX and Z-Score anomaly detection aggressively halt trading during "Black Swan" events.
- **Dynamic Risk:** Fractional Kelly criterion dictates position sizing alongside ATR-based strictly monotonic trailing stops.
- **ML Validation:** Scikit-Learn Random Forest acts as a probability veto threshold.
- **NLP Sentiment:** NLTK VADER parses RSS feeds for fundamental confluence.

## ⚙️ Installation & Execution

The engine is built to run 24/7 on a Linux environment (WSL/Ubuntu) using Docker.

1. **Clone & Configure:**
   ```bash
   cp .env.example .env
   # Edit .env and add your TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID
   ```
2. **Start the Engine:**
   ```bash
   ./manage_bot.sh start
   ```
3. **Monitor Logs:**
   ```bash
   ./manage_bot.sh logs
   ```
