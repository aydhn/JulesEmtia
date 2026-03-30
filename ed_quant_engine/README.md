# ED Capital Quant Engine 🚀

A robust, low-frequency (Multi-Timeframe), autonomous algorithmic trading engine built for the Commodities and TRY-based Forex universe. Designed with strict risk management, zero budget API constraints, and a highly resilient Dockerized architecture.

## Overview
This engine is built on 25 distinct phases combining mathematical edge with institutional risk management.
- **Goal:** High Win-Rate, low frequency trading optimizing for the Kelly Criterion.
- **Budget:** Zero. Relies completely on `yfinance`, free RSS feeds, and local SQLite/ML processing.
- **Architecture:** SOLID Principles, Abstract Broker Layer, and Async Event Loops.

## Key Features
1. **Multi-Timeframe (MTF) Analysis:** 1D for Macro Trend Veto, 1H for Precision Entry (Zero Lookahead Bias).
2. **Machine Learning Validation:** Local Random Forest classifier to veto statistically low-probability setups.
3. **NLP Sentiment Veto:** RSS news sentiment analysis using NLTK VADER.
4. **Institutional Risk Management:**
   - VIX Black Swan Circuit Breaker.
   - Z-Score Micro Flash Crash Detection.
   - Fractional Kelly Position Sizing.
   - Dynamic ATR-based Monotonic Trailing Stops.
   - Global Portfolio Correlation Vetos.
5. **Robust Operations:**
   - SQLite State Recovery.
   - Telegram Admin Commands (`/durum`, `/durdur`, `/kapat_hepsi`).
   - Background Docker Compose Service.
   - ED Capital Tear Sheet Reports (Monte Carlo Risk of Ruin included).

## Installation

1. **Clone the repository and set up a Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   Copy `.env.example` to `.env` and configure your Telegram credentials.
   ```bash
   cp .env.example .env
   # Edit .env to add TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID
   ```

3. **Run using Docker (Recommended for 24/7 Production):**
   ```bash
   chmod +x manage_bot.sh
   ./manage_bot.sh start
   ```

## Admin Commands (Telegram)
- `/durum`: Check balance, open positions, and VIX status.
- `/durdur`: Pause new entries (Trailing stops will continue).
- `/devam`: Resume signal scanning.
- `/kapat_hepsi`: PANIC BUTTON. Close all open trades at market.
- `/tara`: Force a scan outside the hourly schedule.

## Code Quality & Linters
All code is structured to comply with PEP-8. Type Hinting is enforced on all core engine methods.
To run formatting checks locally:
```bash
pip install flake8 black
black core/ main.py
flake8 core/ main.py --max-line-length=120
```
