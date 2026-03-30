# ED Capital Quant Engine

## Piyasalara Genel Bakış
Bu proje, Düşük frekans (Low Frequency), çoklu zaman dilimi (MTF), yüksek isabet oranlı (high win-rate) sinyal ve paper trade (sanal portföy yönetimi) botudur.
Bütçe SIFIR olarak planlanmış olup sadece resmi ve ücretsiz Python kütüphaneleri (yfinance, pandas_ta vb.) kullanılmıştır.

## Mimari
- **Data Ingestion**: yfinance üzerinden MTF veri alımı.
- **Features & MTF**: EMA (50, 200), RSI (14), MACD (12,26,9), ATR (14), BB (20,2). Lookahead bias sıfırdır.
- **Makroekonomik Filtre**: DXY ve VIX endeksleri üzerinden piyasa rejimi (Risk-On / Risk-Off).
- **Yapay Zeka (ML)**: Scikit-learn Random Forest modeliyle sinyal doğrulama.
- **NLP Sentiment**: RSS akışlarından haber duyarlılık analizi (VADER).
- **Risk Yönetimi (JP Morgan Standardı)**: Dinamik ATR Stop-Loss, Kelly Kriteri, Başa Baş (Breakeven), İzleyen Stop (Trailing Stop) ve Dinamik Slippage maliyetleri. Korelasyon Matrisi vetosu.
- **Monte Carlo Stres Testi**: Olasılık bazlı iflas (Ruin) hesaplamaları.
- **Kurumsal Raporlama**: ED Capital standardında "Piyasalara Genel Bakış" temalı kümülatif PnL Tear Sheet.

## Kurulum ve Kullanım (Docker)
```bash
# 1. .env Dosyasını Hazırlayın
cp .env.example .env

# 2. Betiği çalıştırın
chmod +x manage_bot.sh
./manage_bot.sh start

# 3. Logları İzleyin
./manage_bot.sh logs
```

## Telegram Komutları (Sadece ADMIN_CHAT_ID)
- `/durum`: Anlık kasa ve pozisyon sayısını verir.
- `/durdur`: Sistemin yeni pozisyon taramasını durdurur. Açık pozisyonları korur.
- `/devam`: Sistemi tekrar tarama moduna alır.
- `/kapat_hepsi`: Tüm açık pozisyonları panik modunda güncel fiyattan kapatır.
- `/tara`: Saat başını beklemeden zorunlu (Force) tarama başlatır.
