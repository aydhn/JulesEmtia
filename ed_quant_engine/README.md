# ED Capital Quant Engine

Profesyonel düzeyde, düşük frekanslı, çoklu zaman dilimli (MTF) bir algoritmik paper-trade motorudur.

## Proje Amacı ve Vizyonu
Emtia ve TL bazlı Forex paritelerinde "Yüksek Win-Rate" hedefiyle çalışan; JP Morgan risk disiplini (dinamik Kelly), Bill Benter'ın istatistiksel üstünlüğü ve no-budget kısıtlamaları altında kurulmuş tamamen bağımsız bir robottur.

## Kullanılan Özellikler
- **Multi-Timeframe Onayı (MTF):** Günlük trende (1D) karşı saatlik (1H) işlem yasaklanır (Sıfır Lookahead Bias).
- **Yapay Zeka (ML) Vetosu:** Teknik sinyaller, Random Forest modeliyle geçmişteki benzer patternlerin başarı ihtimaline göre (örn. %60 başarı) filtrelenir.
- **NLP Duyarlılık Analizi:** Ücretsiz RSS haberleri VADER ile okunur ve teknik sinyalle çelişen makro haberler reddedilir.
- **Risk Disiplini:** Dinamik ATR izleyen stop, Kesirli (Fractional) Kelly pozisyon boyutlandırma ve global portföy korelasyon limitleri uygulanır.
- **Acil Durum (Siyah Kuğu):** VIX veya Flaş Çöküş tespiti anında sistemi durdurur ve pozisyonları korumaya alır.
- **Kurumsal Raporlama:** Her hafta sonu Matplotlib destekli detaylı Tear Sheet (.html) üretir ve Telegram'dan iletir.

## Kurulum
1. `python3 -m venv venv`
2. `source venv/bin/activate`
3. `pip install -r requirements.txt`
4. `.env` dosyasını Telegram Token'ınız ve Chat ID'nizle güncelleyin.
5. Veritabanını başlatmak için: `python paper_db.py`

## Arka Plan Çalıştırma (Systemd / Docker)
Sistem Ubuntu ortamında veya Docker ile tam bağımsız bir *daemon* olarak çalışmak üzere tasarlanmıştır. `docker-compose up -d` ile saniyeler içinde kalıcı hacimlerle (volumes) canlı paper-trade moduna alabilirsiniz.
