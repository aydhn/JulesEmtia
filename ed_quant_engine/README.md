# ED Capital Quant Engine

Profesyonel, modüler, sıfır bütçeli, algoritmik bir düşük frekans (Low-Frequency) portföy yönetim motorudur.
Sistem, Emtia ve TRY bazlı Forex paritelerinde "Yüksek İsabet Oranı" (High Win-Rate) hedefi ile çalışır.

**VİZYON:** JP Morgan risk algısı, Bill Benter matematiksel yaklaşımı ve kurumsal bir mimari (SPL Düzey 3).

## 🚀 Mimari ve Özellikler
1. **Veri Çekimi (Data Ingestion)**: `yfinance` üzerinden Multi-Timeframe (1D HTF, 1H LTF) veri hizalaması (Lookahead Bias korumalı).
2. **Özellik Mühendisliği (Features)**: Pandas-TA ile EMA, MACD, RSI, ATR ve Bollinger bantları hesabı. Flaş çöküşler (Flash Crashes) için Z-Score Anomaly detection.
3. **Piyasa Filtreleri (Filters)**:
   - **VIX Siyah Kuğu Koruması**: VIX > 35 olduğunda devre kesici.
   - **Makro Kıyaslama**: DXY (Dolar Endeksi) ve TNX (Tahvil getirisi) rejim filtrelemesi.
   - **Dinamik Korelasyon**: Riski katlamamak için Pearson Korelasyon matrisi vetosu.
4. **NLP Haber Duyarlılığı (Sentiment)**: NLTK VADER ile RSS feed'lerinden metin analizi (Sentiment Veto).
5. **Makine Öğrenmesi (ML Validator)**: Sinyallerin kazanma ihtimalini ölçen Scikit-Learn `RandomForestClassifier` vetosu.
6. **Kurumsal Portföy Yönetimi (Position Sizing)**: Kelly Kriteri'nin risk azaltılmış "Fractional Kelly" versiyonu ile kasa yönetimi.
7. **Emir İletim Modeli (Execution Model)**: Volatilite bazlı dinamik Spread ve Fiyat Kayması (Slippage) maliyetlerinin SQLite'a yansıtılması. Başa Baş (Breakeven) ve Strictly Monotonic İzleyen Stop (Trailing Stop) ile Kâr Koruma.
8. **Asenkron Otonom Döngü & Telegram**: `python-telegram-bot` ile komut bazlı (/durdur, /durum, /tara) çift yönlü haberleşme.
9. **Kurumsal Raporlama & Risk Testi**: Vektörel Numpy Monte Carlo simülasyonu ile Risk of Ruin hesaplayan ve ED Capital şablonlu HTML Tear Sheet üreten modül.
10. **Dockerization**: İşletim sisteminden bağımsız, kalıcı SQLite veritabanlı `docker-compose` mimarisi.

## ⚙️ Kurulum ve Başlatma (Linux/WSL)
```bash
# Repo'yu klonladıktan sonra:
cd ed_quant_engine

# Çevre Değişkenleri Şablonunu Kopyala ve Doldur
cp .env.template .env
# Edit .env file and set TELEGRAM_BOT_TOKEN and ADMIN_CHAT_ID

# Yönetim Betiğine İzin Ver
chmod +x manage_bot.sh

# Botu Docker üzerinden başlat (Arka plan servisi)
./manage_bot.sh start

# Logları İzle
./manage_bot.sh logs
```
