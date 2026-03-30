# ED Capital Quant Engine

Profesyonel, tamamen otonom ve **SIFIR BÜTÇE** ile çalışan algoritmik bir işlem (Quant Trading) motorudur. Bu sistem, **Yüksek Win-Rate (İsabet Oranı)** ve **Katı Risk Yönetimi (JP Morgan Standardı)** hedeflenerek tasarlanmıştır. Yalnızca ücretsiz API'ler ve Python kütüphaneleri kullanılarak inşa edilmiştir.

## Mimari & Özellikler (25 Fazlık Tam Kapsam)
1. **Çoklu Zaman Dilimi (MTF) Analizi**: Günlük (HTF) ana trend onayı olmadan Saatlik (LTF) sinyaller filtrelenir.
2. **Makine Öğrenmesi (Machine Learning)**: Random Forest algoritması ile düşük olasılıklı sinyaller vetolanır (Otonom hafta sonu eğitimi).
3. **Doğal Dil İşleme (NLP & Sentiment)**: RSS haber başlıkları VADER ile analiz edilir, makroekonomik duyarlılığa ters düşen sinyaller reddedilir.
4. **Devre Kesiciler (Black Swan)**: VIX endeksi fırladığında veya Z-Score tabanlı ani çöküş (Flash Crash) tespit edildiğinde yeni işlemler dondurulur, açık pozisyonlar acil korumaya alınır.
5. **Dinamik Kelly Kriteri**: Kasa büyüklüğü ve geçmiş performansa (Win Rate, PnL oranı) dayalı agresif olmayan (Kesirli Kelly) pozisyon boyutlandırma.
6. **Gerçekçi Maliyet Simülasyonu**: Volatilite (ATR) tabanlı dinamik fiyat kayması (Slippage) ve enstrümana özel Spread makasları giriş/çıkış fiyatlarına net olarak yansıtılır.
7. **Korelasyon Matrisi**: Aynı yönde ve yüksek korelasyonlu çiftlerde riskin katlanmasını engelleyen veto mekanizması.
8. **Başa Baş & İzleyen Stop**: Kâra geçen pozisyonlarda Zarar Kes (SL) seviyesi anaparayı koruyacak şekilde giriş fiyatına veya piyasa arkasından ileriye doğru sürüklenir. Asla geriye çekilmez.
9. **Broker Soyutlama (Abstract Base Class)**: Sistemin ana beyni ile veri tabanı/borsa emir iletimi tamamen ayrıştırılmıştır (SPL Düzey 3 Uyumlu). Canlı borsa bağlantılarına dakikalar içinde entegre edilebilir.
10. **Telegram ile Çift Yönlü İletişim**: Anlık rapor alma, sistemi duraklatma (`/durdur`) veya acil çıkış (`/kapat_hepsi`) gibi kritik emirler güvenli bir şekilde Telegram üzerinden yönetilir.
11. **Monte Carlo Stres Testi**: 10.000 simülasyon ile sistemin "İflas Riski" (Risk of Ruin) ve %99 Güven Aralığında Beklenen Maksimum Düşüşü hesaplanır ve PDF/HTML kurumsal raporlarına işlenir.
12. **Docker Entegrasyonu**: Kendi başına izole bir konteyner olarak, SQLite hacim eşleşmesiyle birlikte kalıcı veri tutarak 7/24 çalışır.

## Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.10+
- Docker ve Docker Compose (Opsiyonel ama tavsiye edilir)
- Telegram Bot Token ve Chat ID (BotFather üzerinden alınır)

### 1. Ortam Değişkenlerini (Env) Ayarlama
Proje kök dizininde bir `.env` dosyası oluşturun ve bilgilerinizi girin:
```env
TELEGRAM_TOKEN=123456789:ABCDefGHiJklMNOpQRsTuVwxYZ
ADMIN_CHAT_ID=987654321
TZ=Europe/Istanbul
```

### 2. Docker Üzerinden Başlatma (Önerilen)
Yönetim betiğini çalıştırılabilir yapın ve Docker ile derleyin:
```bash
chmod +x manage_bot.sh
./manage_bot.sh docker-deploy
```

### 3. Yerel Makinede Başlatma (Systemd veya Tmux)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

*ED Capital Quant Engine, otonom portföy yönetiminin geleceğidir. Geliştirilen bu kod ekosistemi %100 Pythonik, asenkron ve modüler bir mimariyle örülmüştür.*
