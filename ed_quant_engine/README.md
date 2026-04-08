# ED Capital Quant Engine

ED Capital Quant Engine, düşük frekanslı (Low Frequency), yüksek isabet oranlı (High Win-Rate) algoritmik bir işlem (paper trading) botudur. Tamamen ücretsiz veri kaynakları (yfinance) kullanılarak, sıfır bütçeyle, modüler ve kurumsal mimari standartlarında geliştirilmiştir.

## Özellikler

* **Çoklu Zaman Dilimi (MTF) Analizi:** Günlük (1D) trend filtresi ve Saatlik (1H) tetikleyici ile lookahead bias'tan arındırılmış sinyal üretimi.
* **Makroekonomik Filtreler:** DXY ve ABD 10 Yıllık Tahvil getirilerine dayalı piyasa rejimi (Risk-On/Off) tespiti ve Black Swan (VIX Devre Kesici) koruması.
* **Makine Öğrenmesi Onayı:** Üretilen sinyallerin geçmişteki başarı oranını test eden Random Forest Classifier destekli yapay zeka vetosu.
* **Haber Duyarlılığı (NLP Sentiment):** RSS beslemelerinden VADER ile hesaplanan haber duyarlılığı ve teknik sinyallerle uyuşmazlık (divergence) filtresi.
* **Dinamik Risk ve Kasa Yönetimi:** Kelly Kriteri (Fractional Kelly) ile pozisyon boyutlandırma, ATR tabanlı Dinamik İzleyen Stop (Trailing Stop) ve Başa Baş (Breakeven) mantığı.
* **Broker Soyutlama Katmanı (BAL):** Gerçek broker API'lerine kolayca geçiş yapmayı sağlayan SPL Düzey 3 standartlarında emir iletim mimarisi.
* **Kurumsal Raporlama:** Matplotlib ve Seaborn ile oluşturulmuş, "ED Capital Kurumsal Şablonu"na uygun PDF/HTML Tear Sheet üretim modülü.
* **Telegram Entegrasyonu:** Botu durdurma, başlatma, açık pozisyonları anında kapama (/kapat_hepsi) ve rapor alma gibi çift yönlü kontrol komutları.

## Kurulum ve Çalıştırma

1. **Gereksinimler:** Docker ve Docker Compose kurulu olmalıdır.
2. **Ortam Değişkenleri:** `.env.example` dosyasını kopyalayarak `.env` dosyası oluşturun ve `TELEGRAM_BOT_TOKEN`, `ADMIN_CHAT_ID` bilgilerinizi girin.
3. **Başlatma:** Botu arka planda başlatmak için `./manage_bot.sh start` komutunu çalıştırın.
4. **Loglar:** Logları anlık izlemek için `./manage_bot.sh logs` komutunu kullanabilirsiniz.

## Güvenlik ve Uyarılar
Bu bot şu anda **SADECE PAPER TRADING** (sanal para) ile çalışmaktadır. `data/paper_db.sqlite3` dosyası otomatik olarak oluşturulacak ve tüm işlem geçmişiniz burada tutulacaktır (Docker volumeleri ile kalıcı hale getirilmiştir). Herhangi bir gerçek para işlemi yapmak için `src/broker.py` içerisindeki `BaseBroker` sınıfını miras alan yeni bir sınıf yazmanız gerekmektedir.
