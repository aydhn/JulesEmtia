# ED Capital Quant Engine

A high-performance, modular, and low-frequency algorithmic trading engine focusing on win-rate optimization.
Built entirely with free, open-source libraries and APIs. Benchmark: TÜFE, US CPI, and USD/TRY.

## Key Features
1. **Multi-Timeframe Confluence (MTF)**: Daily trends (1D) guide Hourly execution (1H), eliminating lookahead bias.
2. **Dynamic Risk Management (JP Morgan Framework)**: ATR-based Trailing Stops and Breakeven logic ensures strictly monotonic stops.
3. **Kelly Criterion Position Sizing**: Fractional Kelly allocations prevent risk of ruin.
4. **Machine Learning Validator**: Random Forest classifier filters out statistically improbable signals.
5. **Macro & Sentiment Veto**: Integrates VIX circuit breakers, Flash Crash Z-Score protection, and NLP-based sentiment filtering.
6. **Execution Simulation**: Applies asset-specific spread and dynamic volatility slippage to backtests and paper trades.
7. **Broker Abstraction Layer**: Solid `BaseBroker` implementation for seamless transition from SQLite `PaperBroker` to live environments with SPL Level 3 Audit Trails.
8. **DevOps**: Docker containerized, Systemd-ready, with SQLite/Log persistence and Two-Way Telegram command overrides.

## Deployment

1. Clone repository and create `.env` using `.env.example`.
2. Configure your Telegram BOT_TOKEN and ADMIN_CHAT_ID.
3. Use the management script to build and run the daemon in the background:
```bash
./manage_bot.sh start
```

Use `/durum` or `/tara` via your Telegram Bot.
