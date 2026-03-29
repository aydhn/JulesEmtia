# ED Capital Quant Engine 🚀

A modular, zero-budget, high-win-rate, low-frequency algorithmic paper trading bot engineered for professional quantitative standards.

## 📌 Features (Phases 1-25)
* **Zero Budget Ecosystem:** Uses only free APIs (`yfinance`, `pandas_ta`, `NLTK RSS feeds`). No scraping.
* **MTF Confluence:** Validates signals across Hourly and Daily timeframes without lookahead bias.
* **Risk Management:**
  * Dynamic ATR Trailing Stops & Breakeven logic.
  * Fractional Kelly Criterion position sizing.
  * Correlation Veto to prevent duplicate portfolio risk.
* **Circuit Breakers (Black Swan):** Halts trading automatically when VIX > 30 or flash crash Z-Scores are detected.
* **Machine Learning Validation:** Uses `RandomForestClassifier` to veto low-probability setups based on historical data.
* **NLP News Sentiment:** Filters trades against the prevailing macro news sentiment using `NLTK VADER`.
* **Broker Abstraction Layer (SOLID):** Pluggable architecture ready for live broker execution (currently connected to `PaperBroker` over SQLite).
* **Two-Way Telegram UI:** Execute `/durum`, `/durdur`, `/kapat_hepsi` panic buttons right from your phone.
* **Kurumsal Raporlama:** Automatically generates "Piyasalara Genel Bakış" PDF/HTML Tear Sheets.
* **Dockerized Daemon:** Runs 24/7 on Ubuntu/WSL via `docker-compose` with full state-recovery logic.

## 🛠️ Setup & Deployment

1. **Clone & Configure:**
```bash
git clone https://...
cd ed_quant_engine
```

2. **Create the `.env` file:**
Create a `.env` file in the root directory and add your credentials:
```env
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
ADMIN_CHAT_ID="your_telegram_chat_id"
```

3. **Deploy the Engine:**
Run the deployment script to build the Docker image and start the background daemon:
```bash
./deploy.sh
```

4. **Monitor:**
Check the live logs:
```bash
docker logs -f ed_quant_engine
```
Or simply wait for Telegram notifications!
