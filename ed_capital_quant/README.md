# ED Capital Quant Engine 🚀

Düşük frekanslı, yüksek isabet odaklı, tamamen Python tabanlı ve sıfır bütçeli bağımsız algoritmik ticaret motoru. Bu proje ED Capital standartlarında risk yönetimi ve raporlama disiplinine göre inşa edilmiştir.

## Mimari & Özellikler (25 Fazlık Serüvenin Özeti)
- **Zero-Budget Veri Akışı:** yfinance üzerinden OHLCV ve makro veriler (VIX, DXY, Tahviller).
- **MTF (Çoklu Zaman Dilimi):** Günlük trend onaylı Saatlik keskin girişler (Sıfır Lookahead Bias).
- **Gelişmiş Risk Yönetimi (JP Morgan Tarzı):**
  - Dinamik ATR tabanlı izleyen stop (Trailing Stop).
  - Breakeven (Başa baş) koruması.
  - Kesirli Kelly Kriteri (Fractional Kelly) ile pozisyon boyutlandırma.
- **Siyah Kuğu Koruması:**
  - VIX endeksi tabanlı devre kesiciler.
  - Z-Score tabanlı flaş çöküş anomalisi tespiti.
- **Gerçekçi Maliyetler:** Varlığa özgü dinamik spread ve volatilite bazlı slippage simülasyonu.
- **Yapay Zeka & NLP Onayı:**
  - Random Forest sınıflandırıcısıyla teknik sinyallerin istatistiksel doğrulanması.
  - NLTK (VADER) ile RSS haber duyarlılığının ölçülüp teknik sinyallerle uyumunun test edilmesi.
- **Güvenli Çift Yönlü İletişim:** Telegram üzerinden raporlama ve acil durum /durdur, /kapat_hepsi komutları.
- **SPL Düzey 3 Raporlama:** Matplotlib ve PDF destekli kurumsal Tear Sheet ve Monte Carlo Risk Analizi.

## Kurulum (Docker Üzerinden)

En kolay ve güvenli kurulum yöntemi Docker kullanmaktır:

1. Depoyu klonlayın.
2. `ed_capital_quant` dizinine girin.
3. `.env.example` dosyasını `.env` olarak kopyalayın ve içerisindeki `TELEGRAM_BOT_TOKEN` ile `ADMIN_CHAT_ID` bilgilerinizi (kendi ID'niz) doldurun.
4. Sisteme çalışma izni verin: `chmod +x manage_bot.sh`
5. Başlatın: `./manage_bot.sh start`

## Klasör Yapısı

- `core/`: Loglama, veritabanı bağlantısı ve Broker (işlem iletim) soyutlaması.
- `data_engine/`: MTF veri çekimi, makro ekonomik veri ve haber/NLP duyarlılık analizleri.
- `strategy/`: Sinyal üretim, teknik indikatörler, ML doğrulaması ve Risk/Kelly boyutlandırması.
- `analysis/`: Rapor üretimi (Tear Sheet), portföy yönetimi (Korelasyon) ve Monte Carlo testleri.
- `db/`, `logs/`, `reports/`, `models/`: Docker kalıcı disk (volume) klasörleri.