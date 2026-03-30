# ED Capital Quant Engine

**ED Capital Quant Engine**, otonom, düşük frekanslı (Low Frequency) ve yüksek isabet oranına (High Win-Rate) odaklanan kurumsal bir algoritmik ticaret ve paper trade motorudur. Proje, tamamen ücretsiz kütüphaneler (Yfinance, TA-Lib, NLTK) ile Python tabanlı modüler bir yapıda (SOLID) geliştirilmiştir.

## Proje Mimarisi
* **Sıfır Bütçe**: Hiçbir ücretli API veya scraping (Selenium/BS4) kullanılmaz.
* **Makro Filtreler**: DXY, ABD 10 Yıllık Tahvil ve VIX devre kesicileri ile ters rüzgarlarda işlem engellenir (Siyah Kuğu koruması).
* **Gelişmiş Risk Yönetimi**: ATR tabanlı Dinamik İzleyen Stop, Fractional Kelly (Kasa Yönetimi), Korelasyon Vetosu ve Monte Carlo İflas Riski (Risk of Ruin) ölçümleri.
* **ML ve NLP Doğrulaması**: YFinance verilerinden türetilen Random Forest modeli ve NLTK VADER ile RSS haberlerinden çekilen Sentiment skorları.

## Kurulum ve Kullanım

### Yerel Kurulum
1. `.env` dosyasını oluşturun:
   `cp .env.template .env`
   İçerisine `TELEGRAM_BOT_TOKEN` ve `ADMIN_CHAT_ID` değerlerini girin.

2. Sanal ortam (venv) oluşturun ve bağımlılıkları yükleyin:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Sistemi Başlatın:
   ```bash
   python main.py
   ```

### Docker Üzerinden Kurulum (Önerilen)
Yönetim betiğini kullanarak tüm konteyner altyapısını ayağa kaldırabilirsiniz:
```bash
./manage_bot.sh start
```

Logları İzlemek için:
```bash
./manage_bot.sh logs
```
