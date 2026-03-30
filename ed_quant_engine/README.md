# ED Capital Quant Engine 🚀

Kurumsal Düzey Algoritmik Ticaret ve Portföy Yönetim Motoru.
Düşük Frekans, Yüksek İsabet Oranı, Katı Risk Yönetimi.

## Özellikler
- **MTF (Multi-Timeframe) Analizi:** Günlük trend, Saatlik giriş. (Sıfır Lookahead Bias)
- **Dinamik Risk Yönetimi:** ATR tabanlı İzleyen Stop (Trailing Stop) ve Başa Baş (Breakeven).
- **Yapay Zeka ve NLP:** Random Forest ile sinyal doğrulaması, NLTK VADER ile RSS Haber duyarlılık vetosu.
- **Kesirli Kelly Kriteri (Fractional Kelly):** Kazanma olasılığına göre matematiksel kasa boyutlandırma.
- **Siyah Kuğu Koruması (VIX & Z-Score):** Piyasa çöktüğünde otomatik kapanan "Devre Kesiciler".
- **Broker Abstraction:** SOLID prensipleriyle sanal (Paper) ve gerçek borsalar (Live) arası anında geçiş.
- **Docker Ready:** %100 izole, Volume Mapping ile kalıcı veri.

## Kurulum ve Çalıştırma

### 1. Ortam Değişkenleri
Proje dizininde `.env` dosyası oluşturun:
```bash
TELEGRAM_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here
```

### 2. Docker Compose İle Çalıştırma
```bash
chmod +x manage_bot.sh
./manage_bot.sh start
```

### 3. Logları İzleme
```bash
./manage_bot.sh logs
```

## Güvenlik Duvarı
Bu motor SPL Düzey 3 güvenlik kurallarına göre çalışır:
- DXY/TNX artışlarında gelişmekte olan piyasalara risk alınmaz.
- Pozisyon korelasyonları .75 üzerindeyse riske girilmez.
- `paper_db.sqlite3` Host makineye bağlanmıştır, konteyner silinse bile data kaybolmaz.\n