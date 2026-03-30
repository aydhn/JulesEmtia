# ED Capital Quant Engine 🚀

![Python Version](https://img.shields.io/badge/python-3.10-blue)
![Architecture](https://img.shields.io/badge/architecture-SOLID-success)
![Risk Management](https://img.shields.io/badge/risk-Fractional%20Kelly-orange)

ED Capital Quant Engine, piyasa gürültüsünden arındırılmış, düşük frekanslı (Low Frequency) ve yüksek isabet oranlı (High Win-Rate) işlem fırsatlarını taramak için sıfırdan inşa edilmiş kurumsal düzeyde bir algoritmik ticaret ve paper-trading motorudur.

Bu mimari; **TESLA vizyonuna, JP Morgan risk algısına ve Bill Benter'ın kuantitatif dehasına** dayanan 25 aşamalı zorlu bir süreç sonucunda yaratılmıştır.

## Mimari Özellikleri

- **Bütçe Sıfır (Zero Cost):** Tüm veri çekimi, makine öğrenmesi ve NLP süreçleri tamamen açık kaynaklı ve ücretsiz kütüphanelerle (yfinance, pandas_ta, scikit-learn, NLTK) sağlanır.
- **Broker Soyutlama (Abstraction Layer):** SOLID prensipleri kullanılarak işlemler `BaseBroker` üzerinden yönetilir. Gelecekte gerçek borsa (Binance, Interactive Brokers) API'lerine geçiş sadece tek satır kod değiştirerek yapılabilir (`PaperBroker` -> `LiveBroker`).
- **Lookahead Bias (Geleceği Görme) Koruması:** Çoklu Zaman Dilimi (MTF) analizleri sırasında saatlik ve günlük veriler kusursuz bir şekilde Pandas `merge_asof(direction='backward')` ile hizalanır. Algoritmanın gelecek veriyi sızdırması matematiksel olarak imkansızdır.
- **Kesirli Kelly (Fractional Kelly) Kasa Yönetimi:** Riske edilecek anapara yüzdesi, geçmiş kazanma/kaybetme olasılıklarına göre dinamik olarak hesaplanır ve JP Morgan güvenlik tamponlarıyla (Half-Kelly, Hard Cap) sınırlandırılır.

## Güvenlik ve Risk Filtreleri

Sistem, bir insan müdahalesine gerek kalmadan anaparayı koruyacak acımasız kalkanlarla donatılmıştır:

1. **VIX Devre Kesici (Circuit Breaker):** VIX > 35 olduğunda veya Siyah Kuğu anormalliklerinde yeni alım işlemleri kilitlenir.
2. **Flaş Çöküş Tespit Edici (Z-Score):** Tekil emtialarda yaşanan anlık %5-10'luk flaş çöküşler Z-Score ile anında tespit edilip o varlık dondurulur.
3. **Makine Öğrenmesi Vetosu:** Random Forest algoritması, teknik göstergelerin başarılı olma ihtimalini hesaplar. Düşük ihtimalli sinyaller acımasızca reddedilir.
4. **Haber Duyarlılık Filtresi (NLP VADER):** Ücretsiz RSS haberleri analiz edilir. Haberlerin genel duygusu ile teknik sinyal ters düşerse, işlem veto edilir.
5. **Korelasyon Riski Duplikasyonu:** Aynı anda birbiriyle >0.75 korelasyona sahip iki farklı varlıkta aynı yöne işlem açılarak risk katlanmaz.
6. **Başa Baş (Breakeven) ve Dinamik İzleyen Stop:** Kâra geçen işlemlerin Stop seviyesi derhal giriş fiyatına (Risk-Free) veya kârı kilitleyecek seviyelere sadece tek yönlü (Strictly Monotonic) olarak çekilir.

## Raporlama ve Stres Testi

- **Monte Carlo Risk Stres Testi:** 10.000 farklı simülasyon üzerinden stratejinin "İflas Riski (Risk of Ruin)" ve %99 güven aralığında "Maksimum Düşüşü (Max Drawdown)" ölçülür.
- **Tear Sheet PDF/HTML Çıktısı:** İşlemlerin sonuçları her hafta kurumsal "ED Capital Şablonu" ile raporlanıp Telegram'a otomatik gönderilir.

## Kurulum ve Dağıtım

### Gereksinimler
- Docker & Docker Compose
- Telegram Bot Token ve Admin Chat ID (BotFather ve IDBot üzerinden alınabilir).

### Kurulum Adımları
1. Proje dizininde `.env.example` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun ve Telegram bilgilerinizi girin.
   ```bash
   cp .env.example .env
   ```
2. Tüm sistemi konteynerleştirilmiş ve izole olarak arka planda çalıştırmak için betiği kullanın:
   ```bash
   chmod +x manage_bot.sh
   ./manage_bot.sh start
   ```
3. Botun durumunu izlemek için:
   ```bash
   ./manage_bot.sh logs
   ```

### Manuel Müdahale (Telegram)
Bot, sadece tanımlı Admin kullanıcısından gelen mesajları dinler. Aşağıdaki komutlarla sistemi anlık yönetebilirsiniz:
- `/durum`: O anki açık pozisyonları ve kâr/zararı raporlar.
- `/durdur`: Sistemin yeni işlem açmasını engeller (Trailing Stop'lar devam eder).
- `/devam`: Otonom MTF tarama sistemini tekrar başlatır.
- `/kapat_hepsi`: Panik tuşudur. Tüm pozisyonları güncel fiyattan kapatır.

---
*ED Capital Quant Engine - The future is algorithmic.*
