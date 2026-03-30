# ED Capital Quant Engine

This is a low-frequency, highly optimized Algorithmic Trading Bot focused on Win-Rate maximization and absolute institutional risk management.

## Architecture

- **Data Ingestion**: Multi-Timeframe (1D/1H) without Lookahead Bias (via Yahoo Finance).
- **Core Strategy**: Moving Average Trend confirmation paired with RSI/MACD/Bollinger Band triggers and Z-Score flash-crash protection.
- **Machine Learning**: Random Forest classification acting as a high-probability Veto gate.
- **Risk Management**: Dynamic ATR-based Trailing Stops, VIX Circuit Breakers, Global Portfolio limits, and Pearson Correlation rejection mechanisms. Fractional Kelly Criterion handles position sizing dynamically based on historical $p$, $b$.
- **Sentiment Engine**: NLTK VADER parsing free RSS news feeds.
- **Execution Engine**: Realistic slippage and spread modeling combined with an abstract Broker Layer (SOLID).
- **Orchestration**: Asynchronous main loop integrating Telegram's robust non-blocking Two-Way communication and daily reporting.

## Requirements
To execute this machine:

1. Populate `.env` with:
   ```env
   TELEGRAM_BOT_TOKEN="Your Bot Token"
   ADMIN_CHAT_ID="Your Telegram Chat ID"
   ```
2. Build and launch the container securely via Docker:
   ```bash
   chmod +x manage_bot.sh
   ./manage_bot.sh start
   ```

*ED Capital Proprietary.*
