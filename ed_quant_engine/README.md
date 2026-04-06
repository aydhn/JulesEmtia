# ED Capital Quant Engine

## Mimarinin Amacı
Düşük frekans (Low Frequency), yüksek isabet oranı (High Win-Rate) ve sıfır bütçe ile çalışan algoritmik bir işlem botudur. Makroekonomik veriler (DXY, ABD 10 Yıllık Tahvil Getirisi), Doğal Dil İşleme (NLP) ile Haber Duyarlılığı ve Makine Öğrenmesi (Random Forest) destekli "Çoklu Zaman Dilimi (MTF)" analizleri kullanır.

## Özellikler
- **Sıfır Bütçe**: Açık kaynak kodlu ve ücretsiz kütüphaneler/API'ler kullanılır.
- **MTF Uyumlu (Lookahead Bias Yok)**: Saatlik sinyaller günlük makro trendlerle filtrelenir.
- **Dinamik Kasa Yönetimi**: Fractional Kelly Criterion kullanılarak portföy riski optimize edilir.
- **Kapsamlı Veto Sistemleri**: Makro rejim, ML model vetosu, NLP duyarlılık vetosu ve varlıklar arası korelasyon vetoları içerir.
- **Devre Kesici (Circuit Breaker)**: VIX sıçramalarına veya Z-Score anomalilerine karşı sistemi kilitler ve mevcut pozisyonları korur.
- **Gerçekçi Simülasyon**: Slippage ve Spread oranları, strateji kârlılığını belirlerken fiyata eklendi.

## Kurulum
1. Repoyu klonlayın ve klasöre girin: `cd ed_quant_engine`
2. `.env.example` dosyasını kopyalayın ve kendi bilgilerinizi girin: `cp .env.example .env`
3. Tüm kütüphaneleri yükleyin: `pip install -r requirements.txt` (Dilerseniz VirtualEnv kullanın).
4. `chmod +x manage_bot.sh` komutu ile yetkilendirin.
5. Botu başlatın: `./manage_bot.sh start`

## Gelişmiş Raporlama & Test
Bot; Tear sheet (HTML), Monte Carlo Simülasyonu ve Walk-Forward Optimization süreçlerini destekler. Yerel ortamda `python backtester.py` ve `python walk_forward.py` ile stratejileri test edebilirsiniz.
