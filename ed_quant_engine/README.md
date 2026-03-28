# ED Capital Quant Engine 🚀

Bu proje, düşük frekanslı (Low Frequency), yüksek isabet oranlı (High Win-Rate), sıfır bütçeli ve tamamen modüler bir Algoritmik İşlem / Paper Trading Motorudur.

## Mimari Özellikler
- **Anti-Lookahead Bias:** Zaman dilimi (MTF) birleştirmelerinde sızıntı sıfıra indirilmiştir.
- **Risk Yönetimi:** Fractional Kelly Kriteri, Dinamik ATR İzleyen Stop ve VIX Siyah Kuğu Devre Kesici.
- **Yapay Zeka:** Random Forest Sinyal Doğrulama ve NLTK VADER Duyarlılık (Sentiment) Analizi.
- **Maliyet Simülasyonu:** Slippage ve Spread hesaplamaları net getiri üzerinden yapılır.
- **Raporlama:** Monte Carlo Stres Testi ve Kurumsal HTML Tear Sheet.

## Kurulum
1. `.env.example` dosyasını `.env` olarak kopyalayın ve Telegram Token bilgilerinizi girin.
2. `docker-compose up -d --build` komutuyla sistemi ayağa kaldırın.
3. Telegram üzerinden `/durum`, `/tara` komutlarıyla sistemi test edin.
