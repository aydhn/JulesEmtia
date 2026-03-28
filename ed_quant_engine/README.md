# ED Capital Quant Engine

Profesyonel, düşük frekanslı (Low Frequency), yüksek isabet oranlı (High Win-Rate) algoritmik ticaret motoru.
Tamamen otonom, sıfır bütçeli (Free APIs) ve kurumsal fon yönetimi (JP Morgan / Bill Benter) vizyonuyla kodlanmıştır.

## Mimari Özellikler (25 Fazlık Tam Entegrasyon)
- **MTF (Çoklu Zaman Dilimi):** Günlük trend onayı ile Saatlik kusursuz giriş.
- **Dinamik Risk Yönetimi:** ATR tabanlı Trailing Stop, Breakeven ve Kesirli Kelly Kriteri (Fractional Kelly).
- **Kurumsal Filtreler:**
  - Makro Rejim (DXY, Tahvil, VIX Devre Kesici)
  - Makine Öğrenmesi (Random Forest - OOS Onayı)
  - Haber Duyarlılığı (NLP VADER - Temel Analiz Vetosu)
  - Korelasyon Matrisi (Risk Duplication Koruması)
- **Gerçekçi Maliyet Motoru:** Dinamik Spread ve Volatilite tabanlı Fiyat Kayması (Slippage) simülasyonu.
- **Monte Carlo Stres Testi:** 10.000 simülasyon ile İflas Riski (Risk of Ruin) kanıtı.
- **Çift Yönlü Telegram Botu:** /durum, /durdur, /kapat_hepsi gibi acil durum komutlarıyla Whitelist kontrollü iletişim.
- **Solid Broker Soyutlama Katmanı:** İstenilen gerçek borsaya anında entegre edilebilir yapı.

## Kurulum ve Dağıtım (Docker)

Sistem kalıcı verilerle (Volumes) ve zaman dilimi senkronizasyonuyla (TZ=Europe/Istanbul) donatılmıştır.

1. `.env.example` dosyasını `.env` olarak kopyalayın ve Telegram Token/Chat ID bilgilerinizi girin.
2. Dağıtım betiğine çalıştırma izni verin ve çalıştırın:
```bash
chmod +x deploy.sh
./deploy.sh
```

Motor artık arka planda 7/24 çalışmakta, saat başı uyanarak analiz yapmakta ve Telegram üzerinden rapor vermektedir.
