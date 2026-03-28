# ED Capital Quant Engine

Profesyonel, düşük frekanslı, yüksek isabet oranlı ve sıfır bütçeli algoritmik paper trade motoru.

## Mimari
- **Veri:** yfinance, feedparser (Haberler)
- **Teknik:** pandas, pandas_ta
- **Risk Yönetimi:** Kelly Kriteri, ATR tabanlı Trailing Stop, Korelasyon Vetosu
- **Makro:** VIX Devre Kesici, Flaş Çöküş Koruması
- **Altyapı:** SQLite, Docker, Python 3.10

## Kurulum ve Çalıştırma

1. `.env.example` dosyasını kopyalayın ve `.env` olarak yeniden adlandırın.
2. `TELEGRAM_BOT_TOKEN` ve `ADMIN_CHAT_ID` değerlerini girin.
3. Arka planda başlatmak için:
   ```bash
   cd devops
   ./manage_bot.sh start
   ```

## Klasör Yapısı
- `core/`: Config, Logger, DB ve Telegram entegrasyonu.
- `data/`: Veri çekimi, Makro filtreler ve NLP sentiment.
- `quant/`: Strateji, İndikatörler, ML Validator ve Portföy Yönetimi.
- `execution/`: Sanal Broker ve Maliyet modellemesi.
- `devops/`: Dockerfile ve Bash scriptleri.
