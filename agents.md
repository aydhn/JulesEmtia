(KESİNLİKLE DAHA FAZLA İNDİKATÖR, STRATEJİ, UYUMSUZLUK DA İÇERMELİ)

Rol ve Vizyon Tanımı: Sen; TESLA CEO'su vizyonuna, JP Morgan Fon Yöneticisi risk algısına, Baş Kıdemli Quant Developer teknik derinliğine ve Bill Benter'ın (en başarılı algoritmik bahisçi) deha ile hayal gücüne sahip, algoritmik ticaret konusunda uzmanlaşmış kıdemli bir yazılım mimarısın.
Benim için , modüler, hataya dayanıklı ve profesyonel bir Python algoritması inşa edeceksin. Bu projeyi ortalama 25 fazda (phase) tamamlayacağız.

Proje Özeti ve Kesin Kısıtlamalar:
* Amaç: Emtia ve Döviz (özellikle TRY bacaklı) evreninde fırsat tarayan, saatte birkaç işlem üreterek "Win Rate" (İsabet Oranı) optimizasyonuna odaklanan, düşük frekanslı (Low Frequency) bir sinyal ve paper trade botu geliştirmek.
* Bütçe: SIFIR. Tüm mimari tamamen ücretsiz araçlar, API'ler (örn. yfinance, pandas_ta vb.) ve kütüphaneler üzerine kurulacaktır. Ücretli hiçbir hizmet (Twitter API, OpenAI API, ücretli RPC, kurumsal veri sağlayıcıları vb.) kullanılmayacaktır.
* Veri Çekme Yöntemi: Kesinlikle web scraping (HTML kazıma, BeautifulSoup, Selenium vb.) KULLANILMAYACAKTIR. Sadece resmi/güvenilir ve ücretsiz Python kütüphaneleri üzerinden veri çekilecektir.
* Donanım: Ortalama bir yerel bilgisayar ve 100 Mbps kablolu internet. Kod, bu kaynakları yormayacak şekilde asenkron veya verimli zamanlanmış (scheduler) döngülerle çalışmalıdır.
* İletişim ve Arayüz: Herhangi bir UI veya Dashboard (Streamlit, Flask vb.) İSTEMİYORUM. Bot arka planda stabil çalışacak, tespit ettiği fırsatları, canlı al-sat sinyallerini ve paper trade sonuçlarını bana anlık olarak Telegram üzerinden bildirecektir. Gerçek emir iletimi yapılmayacak, alımları manuel olarak ben yapacağım.
* Kıyaslama (Benchmark): Botun getiri performansı; Türkiye Enflasyonu (TÜİK), ABD Enflasyonu (CPI) ve Dolar/TL Artışı ile düzenli olarak kıyaslanacaktır.


Phase 1 Görevleri (Proje İskeleti ve Evrenin Tanımlanması): Bu ilk fazda kod yazımından ziyade projenin mimarisini ve işlem evrenini kurmanı istiyorum. Lütfen bana şunları sağla:
1. Klasör ve Dosya Mimarisi: Python projemi lokalimde nasıl yapılandırmalıyım? Bana modüler, temiz kod (clean code) prensiplerine uygun, ölçeklenebilir bir dizin ağacı (directory tree) sun. Hangi dosya ne işe yarayacak kısaca açıkla.
2. Genişletilmiş İşlem Evreni (Tickers): Aşağıdaki temel listeyi zenginleştirerek (Yahoo Finance ticker formatında) eksiksiz bir Python sözlüğü (dictionary) veya listesi hazırla:
   * Değerli Madenler: Altın (GC=F), Gümüş (SI=F), Bakır (HG=F), Paladyum (PA=F), Platin (PL=F).
   * Enerji: Ham Petrol WTI (CL=F), Brent Petrol (BZ=F), Doğalgaz (NG=F), (Isınma Yağı ve Benzin gibi majörleri ekle).
   * Tarım & Softs: Buğday (ZW=F), Mısır (ZC=F), Soya (ZS=F), Kahve (KC=F), Kakao (CC=F), Şeker (SB=F), Pamuk (CT=F), (Canlı Hayvan vb. majörleri ekle).
   * Forex (TL Bazlı): USD/TRY (USDTRY=X), EUR/TRY (EURTRY=X), GBP/TRY (GBPTRY=X), JPY/TRY (JPYTRY=X), CNH/TRY (CNHY=X), (CHF ve AUD gibi majörleri ekle).
3. Requirements.txt: Sadece bu proje boyunca kullanacağımız, tamamen ücretsiz veri çekme, teknik analiz, matematiksel modelleme ve zamanlama kütüphanelerinin bir listesini (gerekçeleriyle) ver.
Lütfen bana bir yapay zeka gibi değil, kıdemli bir Quant Developer mimarı gibi, net ve teknik bir dille yanıt ver.


Phase 2: Veri Motoru, Zamanlayıcı ve Bildirim Altyapısı (Data Ingestion, Scheduling & Notification)
Phase 1'deki mimari ve evren kurulumunu onaylıyorum, harika bir temel attık. Rolünü ve vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) koruyarak Phase 2'ye geçiyoruz.
Bütçemizin sıfır olduğunu ve sistem kaynaklarını optimize etmemiz gerektiğini unutma. Bu fazda, projenin veriyi nasıl çekeceğini, nasıl periyodik çalışacağını ve benimle nasıl iletişim kuracağını kodlamanı istiyorum.
Lütfen aşağıdaki 3 temel modülü (Python kodları ve açıklamalarıyla) oluştur:
1. Veri Motoru (data_loader.py veya mimarine uygun dosya):
* Ücretsiz yfinance kütüphanesini kullanarak Phase 1'de belirlediğimiz Ticker evreninden (Emtia ve TL bazlı Forex) veri çekecek asenkron veya senkron, çok sağlam bir sınıf (class) veya fonksiyon yaz.
* Kritik Kural: API'den dönen hataları (Rate limit, connection timeout), eksik verileri (NaN values), hafta sonu/tatil boşluklarını profesyonel bir Quant gibi yönet. (Örn: Forward fill, loglama, bekle-tekrar dene (exponential backoff) mekanizmaları).
* Veri çekme işlemi bittiğinde temizlenmiş, indekslenmiş bir Pandas DataFrame döndürmeli.
* Düşük frekanslı (saatlik, 4 saatlik, günlük) stratejilere uygun multi-timeframe veri çekebilecek esneklikte olmalı.
2. Telegram Bildirim Sistemi (notifier.py):
* Sıfır maliyet kuralına uygun olarak, Telegram Bot API üzerinden (sadece requests kütüphanesi kullanarak, ağır wrapper'lara gerek kalmadan) bana mesaj gönderecek bir modül yaz.
* Fonksiyon, gönderilecek mesajı (sinyal, sistem hatası, paper trade sonucu) ve token/chat_id bilgilerini (.env dosyasından alarak) parametre olarak alıp Telegram'a iletmeli.
* Eğer mesaj iletilemezse sistemi durdurmamalı, sadece log'a hata düşmeli (Try-Except bloğu).
3. Görev Zamanlayıcı (scheduler.py veya main.py döngüsü):
* Sistemi "saatte bir", "4 saatte bir" veya "günde bir" gibi düşük frekanslarda tetikleyecek, sistemi yormayan bir zamanlayıcı (örn. schedule kütüphanesi veya asyncio.sleep döngüsü) kurgula.
* Sonsuz döngü (while True:) içinde CPU'yu sömürmeyecek şekilde uyku (sleep) moduna geçmesini sağla.
* İlk etapta test edebilmemiz için "her X dakikada bir veri motorunu çalıştır ve Telegram'a 'Sistem Aktif ve Tarama Yapılıyor' mesajı at" şeklinde basit bir test döngüsü oluştur.
Lütfen bu modüllerin kodlarını, birbirleriyle nasıl entegre olacaklarını (import yapıları) ve bir .env dosyası şablonunu (Telegram tokenları için) detaylıca yaz. Açıklamaların tamamen profesyonel ve mimari odaklı olsun.


Phase 3: Özellik Mühendisliği ve Teknik İndikatörler (Feature Engineering & Technical Indicators)
Phase 2 kodlarını başarıyla entegre ettim. Veri motoru, zamanlayıcı ve bildirim altyapısı sorunsuz çalışıyor. Şimdi rolünü (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) maksimum seviyede kullanarak Phase 3'e geçiyoruz.
Bu fazda, çektiğimiz ham OHLCV (Açılış, Yüksek, Düşük, Kapanış, Hacim) verilerini işleyip, yüksek isabet oranlı (high win-rate) sinyaller üretebilmek için matematiksel modellere ve teknik indikatörlere dönüştüreceğiz. Bütçemiz sıfır olduğu için bu işlemleri yerel CPU'muzda, Pandas tabanlı ücretsiz ve hızlı kütüphanelerle (örneğin pandas_ta veya standart numpy/pandas fonksiyonları) yapacağız.
Lütfen aşağıdaki gereksinimleri karşılayan modülü (features.py veya indicators.py) yaz:
1. İndikatör ve Özellik Hesaplama Motoru:
* Veri motorundan gelen temizlenmiş Pandas DataFrame'i parametre olarak alan ve yeni özellik (feature) kolonları ekleyerek döndüren modüler bir fonksiyon (add_features(df)) yaz.
* Düşük frekanslı (saatlik/günlük) stratejimizin "gürültüden arınmış" olması için şu temel indikatörleri kesinlikle koda dahil et:
   * Trend Filtresi: EMA 50 ve EMA 200 (Ana yön tayini için).
   * Momentum & Aşırı Alım/Satım: RSI (14) ve MACD (Standart 12, 26, 9).
   * Volatilite & Risk Yönetimi (JP Morgan Risk Algısı burada devreye giriyor): ATR (14) (Dinamik Stop-Loss ve Take-Profit belirlemek için çok kritik) ve Bollinger Bantları (20, 2).
   * Fiyat Hareketi (Price Action): Bir önceki barın getirisi (Log returns veya % değişim).

(KESİNLİKLE DAHA FAZLA İNDİKATÖR, STRATEJİ, UYUMSUZLUK DA İÇERMELİ)

2. Quant Disiplini ve Veri Temizliği (Kritik Kurallar):
* Lookahead Bias (Geleceği Görme Hatası): Hesaplamaların hiçbirinde gelecekteki bir verinin bugünün satırına sızmasına izin verme. Sinyal üretirken daima kapanmış mumları (shift(1)) baz alacak bir yapı kurgula.
* NaN Yönetimi: İndikatörlerin "lookback" (geriye dönük hesaplama) periyotlarından (örn. EMA 200 için ilk 200 satır) kaynaklanan NaN değerleri profesyonelce temizle (dropna() veya uygun bir strateji). Sinyal modülüne NaN veri gitmemeli.
3. Test Edilebilirlik:
* Modülün düzgün çalışıp çalışmadığını test etmek için data_loader.py'dan (Phase 2) örnek bir veri çekip add_features fonksiyonundan geçiren ve son 5 satırı (tail()) konsola yazdıran küçük bir test bloğu (if __name__ == "__main__":) ekle.
Bana bu kodları, vektörel hesaplama (vectorized operations) prensiplerine uygun, for döngülerinden arındırılmış, son derece hızlı çalışacak şekilde Python dilinde ver. Açıklamalarında neden bu indikatörleri ve bu parametreleri seçtiğini bir Quant mimarı perspektifiyle kısaca açıkla.


Phase 4: Sinyal Üretim Mantığı ve Risk Yönetimi (Signal Generation & Risk Management)
Özellik mühendisliği ve teknik indikatörler modülünü (Phase 3) başarıyla sisteme entegre ettim. Sistem şu an sıfır "lookahead bias" ile tertemiz bir DataFrame üretiyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) konuşturacağın en kritik aşamaya, Phase 4'e geçiyoruz.
Bu fazda, işlenmiş verileri alıp katı kurallara bağlı, piyasa gürültüsünden etkilenmeyen, düşük frekanslı ama isabet oranı (win rate) çok yüksek "Al/Sat" sinyalleri üretecek strateji modülünü (strategy.py) yazmanı istiyorum.
Lütfen aşağıdaki kurallara harfiyen uyarak modülü inşa et:
1. Kesişim ve Onay Mekanizması (Confluence Signal Generation):
* Asla tek bir indikatöre bakarak işleme girme. Bana vektörel operasyonlar (Pandas np.where vb.) kullanarak çoklu onay mekanizması kur.
* Long (Alım) Sinyali Senaryosu: * Fiyat, EMA 50'nin üzerinde olmalı (Ana trend yukarı).
   * RSI(14) aşırı satım bölgesinden (örneğin 30'un altından) yukarı kesmiş olmalı VEYA fiyat Bollinger Alt Bandına dokunup tepki vermiş olmalı.
   * MACD histogramı pozitif bölgeye geçmiş veya sıfırın altında yukarı kesişim (Golden Cross) yapmış olmalı.
* Short (Satış) Sinyali Senaryosu: Yukarıdaki kuralların tam tersi (Trend aşağı, RSI aşırı alımdan dönüyor, MACD negatif kesişim).
* Sinyaller, o anki aktif mumdan değil, kesinlikle kapanmış bir önceki mumdan (shift(1)) teyit alarak üretilmeli.
2. JP Morgan Risk Algısı (Dinamik Risk Yönetimi):
* Sabit yüzdelik stop'lar yerine piyasanın o anki volatilitesine saygı duyan bir yapı kur.
* Her üretilen sinyal için, Phase 3'te hesapladığımız ATR (Average True Range) değerini kullanarak dinamik Zarar Kes (Stop-Loss - SL) ve Kar Al (Take-Profit - TP) seviyeleri belirle.
* Örnek Kurgu: SL = Giriş Fiyatı - (1.5 * ATR), TP = Giriş Fiyatı + (3.0 * ATR). (Risk/Reward oranını en az 1:2 olarak kurgula).
3. Paper Trade & Pozisyon Boyutlandırma (Position Sizing):
* Bot şu an gerçek işlem yapmayacak, ancak bana bildirim gönderirken tam bir fon yöneticisi gibi lot/sözleşme büyüklüğü önermeli.
* Varsayılan bir sanal portföy (Örn: 10.000 USD) belirle. Tek bir işlemde kasanın maksimum %2'sini riske atacak şekilde (Risk Edilen Tutar / Stop Loss Mesafesi) bir "Önerilen Pozisyon Büyüklüğü" hesaplama fonksiyonu yaz.
4. Çıktı Formatı:
* Modül, sadece "Sinyal Var = 1 veya -1" demekle kalmamalı. Sinyal oluştuğunda; Ticker, Yön (Long/Short), Giriş Fiyatı, Dinamik SL, Dinamik TP ve Önerilen Pozisyon Büyüklüğü bilgilerini içeren bir Python Sözlüğü (Dictionary) veya yapılandırılmış bir format döndürmeli. (Bu çıktı Phase 2'deki Telegram bildirim modülüne gönderilecek).
Bana bu sağlam altyapıyı, tamamen Pythonik ve performanslı bir kod yapısıyla sun. Fonksiyonların ne işe yaradığını yorum satırlarında bir Quant Developer gibi açıkla.


Phase 5: Ana Orkestrasyon ve Paper Trade Veritabanı (Main Loop & Paper Trading Engine)
Phase 4'teki strateji ve risk yönetimi modüllerini başarıyla entegre ettim. Sinyallerimiz ve dinamik ATR tabanlı risk hesaplamalarımız kusursuz çalışıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin kalbini atmaya başlatmak için kullanacağın Phase 5'e geçiyoruz.
Bu fazda, şimdiye kadar yazdığımız tüm modülleri (data_loader, notifier, features, strategy) tek bir merkezde birleştiren ana çalışma döngüsünü (main.py) ve işlemlerimizin kaydını tutacak yerel veritabanı altyapısını (paper_db.py) kurmanı istiyorum. Sıfır bütçe kuralımızı hatırlayarak harici bir veritabanı yerine Python'ın dahili kütüphanelerini kullanacağız.
Lütfen aşağıdaki modülleri profesyonel bir mimariyle inşa et:
1. Yerel Paper Trade Veritabanı (paper_db.py):
* Python'ın gömülü sqlite3 kütüphanesini kullanarak hafif ve hızlı bir yerel veritabanı kur. (CSV tabanlı işlemler ileride veri büyüdükçe yavaşlayacağı için SQLite şarttır).
* Veritabanında şu sütunlara sahip bir trades tablosu oluşturan bir başlatma fonksiyonu yaz: trade_id, ticker, direction (Long/Short), entry_time, entry_price, sl_price, tp_price, position_size, status (Open/Closed), exit_time, exit_price, pnl (Kar/Zarar).
* Yeni bir işlem açıldığında veritabanına kayıt ekleyen (open_trade) ve bir işlem kapandığında kaydı güncelleyen (close_trade) iki ayrı fonksiyon yaz.
2. Açık Pozisyon Yöneticisi (Position Tracker):
* Sadece yeni sinyal aramak yetmez. Veritabanındaki "Open" (Açık) statüsündeki işlemleri periyodik olarak kontrol eden bir mekanizma yaz.
* Yeni veri çekildiğinde, açık pozisyonların mevcut fiyatını kontrol edip, fiyat sl_price veya tp_price seviyelerine değdiyse (veya aştıysa) işlemi kapatıp PNL (Kar/Zarar) hesaplasın ve bunu Telegram üzerinden "İşlem Kapandı: Kâr/Zarar = X" şeklinde bana bildirsin.
3. Ana Orkestrasyon ve Döngü (main.py):
* Phase 2'de hazırladığın scheduler altyapısını burada ana döngüye entegre et.
* Sistem her döngüde (örneğin saat başı) şu adımları sırasıyla, asenkron veya performanslı bir şekilde yapmalı:
   1. Tüm Ticker evreni için güncel veriyi çek (data_loader).
   2. Verileri indikatörlerden geçir (features).
   3. Önce Açık Pozisyonları kontrol et (TP/SL patlamış mı?). Kapanan varsa Telegram'a bildir ve SQLite'ı güncelle.
   4. Ardından Yeni Sinyal var mı diye kontrol et (strategy).
   5. Yeni sinyal varsa: SQLite'a "Open" olarak kaydet ve bana Telegram'dan tam teçhizatlı bildirim at (Ticker, Yön, Giriş, SL, TP, Önerilen Lot).
* Kodu herhangi bir hata durumunda (örneğin internet kopması, yfinance API hatası) çökmeyecek şekilde try-except bloklarıyla ve loglama (logging kütüphanesi) ile koruma altına al.
Bana main.py ve paper_db.py içeriklerini, fonksiyonların birbirleriyle nasıl haberleştiğini gösteren temiz (clean code) bir yapıda ver. Quant disiplininden ödün verme.


Phase 6: Makroekonomik Filtreleme, Piyasa Rejimi ve Kıyaslama (Macro Regime & Benchmarking)
Phase 5'teki ana döngü ve SQLite paper trade veritabanı kusursuz bir şekilde entegre oldu. Bot artık otonom olarak tarama yapıyor, pozisyon açıp kapatıyor ve PNL hesaplayarak Telegram'dan bildiriyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) kullanarak sistemi bir üst seviyeye taşıyacağımız Phase 6'ya geçiyoruz.
Bu fazda, sadece teknik indikatörlere körü körüne güvenmek yerine, makroekonomik verileri kullanarak bir "Piyasa Rejimi Filtresi (Market Regime Filter)" oluşturmanı ve ilk başta konuştuğumuz kıyaslama (benchmark) altyapısını kurmanı istiyorum. Sıfır bütçe ve no-scraping kurallarımız geçerli.
Lütfen aşağıdaki özellikleri barındıran modülü (macro_filter.py) ve entegrasyonlarını yaz:
1. Makroekonomik Veri Motoru (Ücretsiz Kaynaklar):
* yfinance veya pandas_datareader (FRED API key gerektirmeyen temel veriler için) kullanarak şu verileri periyodik olarak çekecek bir fonksiyon yaz:
   * DXY (Dolar Endeksi): DX-Y.NYB (Küresel dolar likiditesi ve risk algısı için).
   * ABD 10 Yıllık Tahvil Getirisi: ^TNX (Fırsat maliyeti ve faiz baskısı için).
* Verilerdeki NaN değerleri ve hafta sonu boşluklarını (forward fill ile) temizle.
2. Piyasa Rejimi ve Sinyal Filtreleme (Regime Filter):
* Çekilen bu makro verilerle hareketli ortalamalar (örn. DXY 50 günlük SMA üzerinde mi?) veya momentum hesaplayarak bir piyasa rejimi (Risk-On / Risk-Off / Nötr) belirleyen matematiksel bir kurgu yarat.
* Kritik Entegrasyon: Phase 4'te yazdığın strategy.py içindeki sinyal üretme mantığına bu filtreyi bir "Veto Hakkı" olarak ekle.
   * Örnek Kural: Eğer DXY ve ABD 10 Yıllık Tahvil Getirisi güçlü bir yükseliş trendindeyse (Risk-Off / Sıkılaşma Rejimi), Değerli Madenlerde (Altın, Gümüş) veya gelişmekte olan kurlarda gelen Long (Alım) sinyallerini iptal et (False Positive elemesi). Rüzgara karşı işlem açma.
3. Benchmark (Kıyaslama) Altyapısının Temeli:
* Stratejimizin başarısını ölçmek için ana dosyamızda belirttiğimiz hedeflere (TÜFE ve Dolar/TL) karşı performansımızı izlemeliyiz.
* yfinance üzerinden USDTRY=X verisini kullanarak, botun çalışmaya başladığı günden itibaren Dolar/TL'nin % kaç arttığını (Buy & Hold USDTRY) hesaplayan basit bir fonksiyon yaz.
* Telegram modülünü, haftada bir kez (örneğin Cuma kapanışında) "Haftalık Özet" atacak şekilde güncelle: Botun Toplam PNL'i ile Dolar/TL'nin o haftaki getirisini kıyaslayıp tek mesajda raporlasın. (Türkiye enflasyonu verisi API olmadan zor çekileceğinden şimdilik en büyük rakibimiz Dolar/TL artışıdır).
Bana bu yeni macro_filter.py modülünün kodlarını ve strategy.py ile main.py içerisine bu makro filtreyi ve haftalık raporu bozmadan, clean code prensipleriyle nasıl entegre edeceğimi göster. Açıklamalarında bu filtrelerin mantığını bir fon yöneticisi gibi savun.


Phase 7: Geriye Dönük Test Motoru ve Parametre Optimizasyonu (Historical Backtesting & Optimization)
Phase 6'daki makroekonomik filtreleri ve benchmark altyapısını başarıyla sisteme entegre ettim. Sistem artık DXY veya ABD Tahvil getirilerindeki ters rüzgarları sezip yanlış sinyalleri (false positives) başarıyla filtreliyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer teknik derinliği) stratejimizin doğruluğunu kanıtlamak için kullanacağın Phase 7'ye geçiyoruz.
Bu fazda, yazdığımız stratejinin geçmiş veriler üzerinde (örneğin son 5 yıl) ne kadar kârlı olduğunu ve hedeflenen "Yüksek İsabet Oranı (High Win-Rate)" kurgusuna ulaşıp ulaşmadığını ölçeceğimiz bir backtester.py modülü yazmanı istiyorum. Bütçemiz sıfır, donanımımız ortalama bir bilgisayar. Bu nedenle dışarıdan ağır kütüphaneler (Backtrader vb.) kurmak yerine, elimizdeki Pandas DataFrame yapısını kullanarak son derece hızlı, vektörel (vectorized) veya basit iteratif bir backtest altyapısı kuracağız.
Lütfen aşağıdaki gereksinimleri karşılayan backtester.py modülünü yaz:
1. Vektörel veya Hızlı İteratif Backtest Motoru:
* data_loader.py ile çekilen uzun vadeli (örn. 5 yıllık) geçmiş veriyi, features.py (indikatörler) ve macro_filter.py (piyasa rejimi) modüllerinden geçir.
* strategy.py içindeki kuralları geçmiş veriye uygulayarak sanal giriş (entry), kar al (TP) ve zarar kes (SL) noktalarını hesapla.
* Kritik Kural (Gerçekçilik): Gerçek dünyadaki kaymaları simüle etmek için her işleme %0.1 "Slippage" (Fiyat Kayması) ve %0.05 "Komisyon" maliyeti ekle. İşlemler asla kusursuz fiyattan gerçekleşmez.
2. Performans Metrikleri (Quant Raporlaması):
* Backtest tamamlandığında sadece "Şu kadar kâr ettin" demek yerine, profesyonel bir fon raporu gibi şu metrikleri hesaplayan bir fonksiyon yaz:
   * Win Rate (İsabet Oranı): Kârlı kapanan işlemlerin toplam işlemlere oranı (Hedefimiz en az %60-65).
   * Profit Factor (Kâr Faktörü): Brüt Kâr / Brüt Zarar (1.5 üzeri hedeflenir).
   * Max Drawdown (Maksimum Düşüş): Tepeden dibe portföyün gördüğü en büyük erime yüzdesi.
   * Total PnL vs Benchmark: Stratejinin net getirisi ile aynı dönemdeki USD/TRY (Buy & Hold) getirisinin kıyaslaması.
3. CPU Dostu Parametre Optimizasyonu (Grid Search):
* Stratejimizin parametreleri (Örn: RSI aşırı satım eşiği 30 mu olmalı 25 mi? SL için ATR çarpanı 1.5 mi olmalı 2.0 mi?) sabittir. Bunların en iyisini bulmak için bir optimizasyon fonksiyonu yaz.
* Ortalama bir donanım kullandığımızı ve kodların WSL/Ubuntu ortamında çalıştırılabileceğini göz önünde bulundurarak, CPU'yu boğmayacak dar kapsamlı bir Grid Search (Izgara Araması) kurgula. İşlemleri paralelleştirmek için Python'ın yerleşik multiprocessing veya concurrent.futures kütüphanelerinden faydalanabilirsin.
* Fonksiyon, belirlenen Ticker evreni için en iyi parametre kombinasyonlarını bulup terminale şık bir tablo olarak (Pandas yardımıyla) yazdırmalı.
Bana bu modülü, dışa bağımlılığı minimumda tutan, clean code prensiplerine sadık ve matematiksel olarak kusursuz bir yapıda sun.


Phase 8: Hata Yönetimi, Otonom İyileşme ve Profesyonel Loglama (Error Handling, Self-Healing & Logging)
Phase 7'deki Backtest ve Optimizasyon motorunu başarıyla entegre ettim. Sistem artık geçmiş verilerde %60+ win-rate hedefini test edebiliyor ve parametreleri optimize edebiliyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer teknik derinliği) sistemin "ölümsüzlüğünü" sağlamak için kullanacağın Phase 8'e geçiyoruz.
Bir fon yöneticisi için en büyük kabus, sistemin açık bir pozisyondayken çökmesi ve Stop-Loss emirlerinin sahipsiz kalmasıdır. Ortalama bir yerel bilgisayarda ve standart bir internet bağlantısında çalıştığımızı unutma. Kesintiler olacaktır.
Lütfen sistemi kesintilere karşı %100 dayanıklı hale getirecek aşağıdaki modülleri (logger.py ve sistem geneli güncellemeler) yaz:
1. Profesyonel Loglama Altyapısı (logger.py):
* Standart print() komutlarını tamamen çöpe atıyoruz. Python'ın dahili logging kütüphanesini kullanarak asenkron/senkron çalışmaya uygun bir loglama modülü yaz.
* Diski doldurmamak için RotatingFileHandler (örneğin maksimum 5 MB'lık 3 yedek dosya) kullan.
* Hata seviyelerini (INFO, WARNING, ERROR, CRITICAL) net bir şekilde ayır. Kritik hatalarda (CRITICAL) mutlaka Telegram modülünü (notifier.py) tetikleyerek bana acil durum mesajı at.
2. Otonom İyileşme ve Retry (Yeniden Deneme) Mekanizması:
* Ücretsiz yfinance API'si bazen rate-limit (istek sınırı) yiyebilir veya "Connection Timeout" verebilir.
* Veri çekme (data_loader.py) ve mesaj gönderme (notifier.py) fonksiyonlarını sarmalayacak (decorator olarak veya try-except içinde) bir Exponential Backoff (Kademeli Bekleme) algoritması yaz.
* Örnek: İstek başarısız olursa çökme; 1 dakika bekle tekrar dene, yine başarısız olursa 2 dakika, sonra 4 dakika bekle. 3. denemede de başarısız olursa bunu bir WARNING olarak logla ve o döngüyü atla (fakat programı kapatma).
3. Durum Kurtarma (State Recovery) - Kritik:
* Diyelim ki elektrik kesildi ve bilgisayar yeniden başladı. Bot main.py üzerinden tekrar ayağa kalktığında, hiçbir şey olmamış gibi sıfırdan başlamamalıdır.
* main.py başlatıldığında ilk iş olarak paper_db.py (SQLite) üzerinden status = 'Open' olan tüm pozisyonları okuyup hafızasına (memory) alacak bir "Recovery" (Kurtarma) fonksiyonu yaz. Böylece yeniden başlasa bile eski açık pozisyonların TP/SL takibine kaldığı yerden devam edebilsin.
4. Canlılık Sinyali (Heartbeat):
* Botun sessizce çökmediğinden emin olmak için main.py döngüsüne bir "Heartbeat" ekle.
* Her gün sabah 08:00'de (veya belirlenen bir saatte) Telegram üzerinden bana "🟢 Sistem Aktif: Son 24 saatte X döngü tamamlandı, Y API hatası tolere edildi, Z adet açık pozisyon takip ediliyor." şeklinde kısa bir durum raporu atsın.
Bana bu sağlamlaştırma kodlarını, clean code prensiplerine uygun, mevcut mimariyi bozmayacak şekilde nasıl entegre edeceğimi detaylıca anlat.


Phase 9: Arka Plan Servisi, Sürekli Çalışma ve İşletim Sistemi Entegrasyonu (Background Execution & Systemd/Tmux)
Phase 8'deki otonom iyileşme, heartbeat (canlılık sinyali) ve durum kurtarma (state recovery) modüllerini başarıyla sisteme entegre ettim. Bot artık bağlantı kopsa da çökmüyor, kapanıp açılsa bile açık pozisyonları hafızasına geri alıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin kalıcılığını sağlamak için kullanacağın Phase 9'a geçiyoruz.
Profesyonel bir işlem botu, kullanıcının aktif bir terminal penceresine bağımlı kalamaz. Bu botu, Ubuntu/Linux (WSL vb.) ortamında arka planda 7/24 kesintisiz çalışacak, bilgisayar yeniden başladığında otomatik olarak tetiklenecek bir sistem servisi haline getirmeliyiz.
Lütfen bana şu entegrasyon dosyalarını ve komutlarını profesyonel bir Quant altyapısına uygun şekilde hazırla:
1. Systemd Servis Dosyası (quant_bot.service):
* Linux systemd altyapısı için bir servis dosyası yaz.
* Bu servis; bot çökerse otomatik olarak yeniden başlamalı (Restart=always),
* Sanal ortamı (virtual environment) doğru bir şekilde hedef almalı ve main.py'yi çalıştırmalıdır.
* Standart çıktıları ve hata loglarını sistemin journalctl yapısına veya Phase 8'de kurduğumuz log dosyasına düzgünce aktaracak parametreleri içermelidir.
2. Başlatma ve Yönetim Betiği (manage_bot.sh):
* Benim sürekli uzun terminal komutları yazmamam için, botu yönetecek tek bir bash script hazırla.
* Bu script içinde; botu başlatma (start), durdurma (stop), yeniden başlatma (restart), logları canlı izleme (logs) ve durumunu kontrol etme (status) gibi fonksiyonlar/argümanlar olsun.
* Örnek kullanım hedefi: ./manage_bot.sh start veya ./manage_bot.sh logs
3. Alternatif Session Yönetimi (Tmux / Screen - Fallback):
* Eğer sistemde systemd kullanılamıyorsa (örneğin kısıtlı bir WSL sürümü), botu güvenli bir şekilde arka planda tutacak en optimal tmux komut dizisini de bir B-Planı olarak bana sağla.
Bana bu dosyaların içeriklerini ve bunları sistemime tam olarak nasıl kuracağımı (dosya izinleri chmod +x, servisi enable etme vb.) adım adım, hataya yer bırakmayacak bir netlikte ver.


Phase 10: Kod Temizliği, Güvenlik Denetimi ve Versiyon Kontrolü (Refactoring, Security & Git)
Phase 9'daki Systemd/Tmux arka plan servisi entegrasyonunu başarıyla tamamladım. Bot artık Ubuntu/WSL üzerinde tam bağımsız bir "daemon" olarak, terminal kapalıyken bile çalışıyor ve çökmelere karşı kendini koruyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) kurumsal yazılım standartlarını projeye entegre etmek için kullanacağın Phase 10'a geçiyoruz.
Profesyonel bir Quant projesi, dağınık kodları ve güvenlik açıklarını kabul etmez. Kodu GitHub'a veya yerel bir depoya (repository) aktarmadan önce son bir temizlik ve güvenlik kalkanı oluşturmamız gerekiyor.
Lütfen aşağıdaki kurumsal standartları projeye uygulamam için gerekli adımları ve dosyaları hazırla:
1. Katı Güvenlik ve .gitignore Yapılandırması:
* Proje dizininde asla şifre veya API anahtarı (Telegram Token vb.) barındırmayacağız. .env dosyasının kullanımını standartlaştır.
* Python, WSL ortamı ve VS Code için eksiksiz bir .gitignore dosyası oluştur. Bu dosya kesinlikle şunları dışlamalıdır:
   * .env dosyası (Kritik).
   * paper_db.py tarafından oluşturulan yerel SQLite veritabanı dosyası (.db, .sqlite3).
   * Phase 8'de oluşturulan log dosyaları (.log vb.).
   * Python önbellek dosyaları (__pycache__, .pyc).
   * VS Code yapılandırma klasörleri (.vscode/).
2. Type Hinting (Tip Belirleme) ve PEP 8 Standartları:
* Şu ana kadar yazdığımız data_loader.py, features.py, strategy.py, paper_db.py ve main.py dosyalarındaki tüm ana fonksiyonlar için Python Type Hinting (örneğin def calculate_rsi(df: pd.DataFrame, period: int) -> pd.DataFrame:) standartlarını zorunlu kıl.
* Bana, yazdığımız kodları PEP 8 standartlarına (clean code) uygun hale getirmek için kullanabileceğim ücretsiz linting/formatting araçlarını (örneğin black, flake8 veya ruff) ve bunları projede nasıl hızlıca çalıştıracağımı (komut satırı örneği) göster.
3. Profesyonel Quant README.md Dosyası:
* Projenin kök dizini için son derece şık, Markdown formatında bir README.md yaz.
* Bu belge şunları içermelidir:
   * Projenin mimarisi ve amacı (Düşük frekans, yüksek win-rate, sıfır bütçe).
   * Kullanılan indikatörler ve makroekonomik filtrelerin (DXY, Tahvil getirileri) kısa özeti.
   * Kurulum adımları (Sanal ortam oluşturma, requirements.txt yükleme).
   * Arka plan servisinin (manage_bot.sh veya systemd) nasıl çalıştırılacağı.
Bana bu güvenlik konfigürasyonlarını, .gitignore içeriğini ve README.md şablonunu bir baş mühendis titizliğiyle sun.


Phase 11: Gelişmiş Portföy Yönetimi ve Dinamik Korelasyon Matrisi (Advanced Portfolio Allocation & Correlation Engine)
Phase 10'daki kod temizliği, PEP 8 standartları ve güvenlik (Git/Env) yapılandırmalarını başarıyla tamamladım. Proje artık kurumsal bir altyapıya sahip. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) portföy seviyesinde riski yönetmek için kullanacağın Phase 11'e geçiyoruz.
Tekil işlemlerde isabet oranımız yüksek olsa da, yüksek korelasyonlu varlıklarda aynı anda pozisyon açmak portföy riskimizi (Exposure) katlayacaktır. Bu fazda, sıfır bütçe kuralımıza sadık kalarak pandas üzerinden dinamik bir korelasyon motoru yazmanı ve bunu sinyal onay mekanizmasına bir "Son Veto" olarak eklemeni istiyorum.
Lütfen aşağıdaki özellikleri barındıran modülü (portfolio_manager.py) ve gerekli entegrasyonları yaz:
1. Dinamik Korelasyon Motoru:
* Ticker evrenimizdeki tüm varlıkların günlük kapanış fiyatlarını kullanarak son 30 veya 60 günlük periyotta yuvarlanan (rolling) bir Pearson Korelasyon Matrisi hesaplayan bir fonksiyon yaz (calculate_correlation_matrix()).
* Fonksiyon, birbirine yüksek oranda bağlı varlık çiftlerini (örneğin korelasyon katsayısı > 0.75 veya < -0.75 olanlar) tespit edebilmelidir.
2. Korelasyon Vetosu (Risk Duplication Filter):
* strategy.py'den bir sinyal (örneğin Gümüş için Long) geldiğinde, portfolio_manager.py devreye girmeli.
* Önce paper_db.py üzerinden halihazırda açık olan pozisyonlara (örneğin Altın Long var mı?) bakmalı.
* Eğer açık pozisyondaki varlık ile yeni sinyal gelen varlık arasındaki korelasyon eşik değerin (örn. +0.75) üzerindeyse ve yönler aynıysa (ikisi de Long), riski ikiye katlamamak için yeni sinyali reddetmeli (Veto).
* Ters korelasyon durumunu da hesaba kat (örn. biri +0.80 korelasyonlu ama biri Long diğeri Short ise bu bir risk azaltıcı hedge olabilir, buna izin verilebilir veya stratejiye göre reddedilebilir. Lütfen Quant mantığıyla en güvenli senaryoyu kurgula).
3. Maksimum Risk ve Pozisyon Sınırı (Global Exposure Limit):
* Sistem ne kadar iyi sinyal üretirse üretsin, sanal kasanın tamamını aynı anda piyasaya sürmemeliyiz.
* Toplam açık pozisyon sayısını (örneğin maksimum 3 veya 4) ve toplam riske edilen kasa yüzdesini (örneğin toplam kasanın maksimum %6'sı) sınırlandıran bir global limit fonksiyonu yaz.
* Limitler doluysa, yeni gelen mükemmel bir sinyal bile olsa "Kapasite Dolu" gerekçesiyle reddedilip loglanmalıdır.
Bana bu portfolio_manager.py modülünün kodlarını ve main.py içindeki ana döngüye, tam sinyal işleme alınmadan hemen önce (execution öncesi) nasıl kusursuzca entegre edileceğini anlat. Loglamaları (logger.py) unutma, reddedilen sinyallerin neden reddedildiği loglara detaylıca düşmeli.


Phase 12: Dinamik İzleyen Stop ve Kâr Koruma Mekanizması (Trailing Stop & Trade Management)
Phase 11'deki portföy yönetimi, korelasyon matrisi ve global risk limitlerini başarıyla sisteme entegre ettim. Bot artık aynı risk grubuna ait varlıklarda riski katlamıyor ve pozisyon limitlerine harfiyen uyuyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) anaparayı ve elde edilen kârı korumak için kullanacağın Phase 12'ye geçiyoruz.
Kurumsal portföy yönetimi standartlarında, kâra geçmiş bir işlemin zararla kapanması kabul edilemez. Bu fazda, main.py içindeki açık pozisyon takip mekanizmasını ve paper_db.py veritabanını güncelleyerek "Trailing Stop" (İzleyen Stop) ve "Breakeven" (Başa Baş) mantığını koda dökeceğiz.
Lütfen aşağıdaki kâr koruma algoritmalarını ve entegrasyonlarını yaz:
1. Başa Baş (Breakeven) Noktasına Çekme:
* İşlem belirli bir kârlılık seviyesine ulaştığında (Örneğin, fiyat giriş fiyatından +1.0 ATR veya Risk'in %50'si kadar lehimize hareket ettiğinde), Zarar-Kes (SL) seviyesini derhal Giriş Fiyatına (Entry Price) çek.
* Bu gerçekleştiğinde işlemi "Risksiz (Risk-Free)" olarak işaretle ve veritabanını (paper_db.py) yeni SL fiyatıyla güncelle.
2. ATR Tabanlı Dinamik İzleyen Stop (Trailing Stop):
* Fiyat lehimize gitmeye devam ettikçe, Stop-Loss seviyesi de fiyatın arkasından yukarı (Long için) veya aşağı (Short için) dinamik olarak kaydırılmalıdır.
* Fiyat yeni bir zirve (Long) veya yeni bir dip (Short) yaptığında, yeni SL seviyesini Zirve Fiyat - (1.5 * ATR) veya Dip Fiyat + (1.5 * ATR) olarak hesapla.
* Kritik Kural: Stop-Loss sadece kâr yönünde hareket edebilir. Fiyat gerilediğinde SL seviyesi asla geriye çekilmemelidir (Strictly monotonic). Yeni hesaplanan SL, mevcut SL'den daha kötüyse güncelleme yapma.
3. Veritabanı ve Ana Döngü Entegrasyonu:
* paper_db.py dosyasına, açık bir işlemin sl_price değerini güncelleyecek yeni bir fonksiyon (update_sl_price(trade_id, new_sl)) ekle.
* main.py içindeki "Açık Pozisyonları Kontrol Et" adımını revize et. Sistem artık sadece TP/SL patlamış mı diye bakmamalı; patlamadıysa "SL seviyesini lehimize revize etmeli miyim?" diye kontrol etmeli.
4. Bildirim Yönetimi:
* SL seviyesi Başa Baş (Breakeven) noktasına çekildiğinde veya İzleyen Stop ile kâr kilitlendiğinde, Telegram modülü (notifier.py) üzerinden bana "🔒 Risk Sıfırlandı: [Ticker] SL seviyesi giriş fiyatına çekildi" gibi kısa bir bilgilendirme mesajı at.
Bana bu mekanizmayı, sistemin performansını düşürmeyecek vektörel/hızlı hesaplamalarla ve temiz kod prensipleriyle (PEP 8) nasıl uygulayacağımı anlat.


Phase 13: Kurumsal Raporlama ve Performans Özeti (Tear Sheet Generation)
Phase 12'deki İzleyen Stop (Trailing Stop) ve Başa Baş (Breakeven) kâr koruma algoritmalarını başarıyla entegre ettim. Sistem artık kâra geçen işlemlerde anaparayı asla riske atmıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) elde ettiğimiz bu kusursuz verileri kurumsal bir dille sunmak için kullanacağın Phase 13'e geçiyoruz.
Profesyonel portföy yönetiminde, yatırımcıya veya komiteye sunulacak raporun kalitesi, stratejinin kalitesi kadar önemlidir. Senden, botun ürettiği verileri okuyup görsel ve metinsel bir "Tear Sheet" (Performans Raporu) hazırlayacak reporter.py modülünü yazmanı istiyorum.
Lütfen aşağıdaki kurumsal standartlara harfiyen uy:
1. Rapor Şablonu ve İsimlendirme Standartları:
* Raporun görsel ve yapısal dizaynı kesinlikle ED Capital Kurumsal Şablonu standartlarında ve ciddiyetinde olmalıdır.
* Raporun en üstünde yer alan ana özet başlığı kesinlikle "Yönetici Özeti" gibi amatör/standart ifadeler KULLANILMAYACAK, bunun yerine doğrudan "Piyasalara Genel Bakış" başlığı kullanılacaktır.
2. Veri Çekme ve Metrik Hesaplama:
* paper_db.py içerisindeki SQLite veritabanından kapalı (Closed) statüsündeki tüm işlemleri Pandas DataFrame olarak çek.
* Raporda bulunması gereken temel metrikler (Quant dilli):
   * Başlangıç Bakiyesi ve Güncel Bakiye
   * Toplam PnL (Net Kâr/Zarar)
   * Win Rate (İsabet Oranı)
   * Profit Factor (Kâr Faktörü: Brüt Kâr / Brüt Zarar)
   * Max Drawdown (Maksimum Düşüş)
   * İşlem Başına Ortalama Kâr ve Ortalama Zarar (Average Win / Average Loss)
3. Görselleştirme (Matplotlib / Seaborn):
* Bütçemiz sıfır olduğu için Python'ın yerleşik ve ücretsiz görselleştirme kütüphanelerini kullanarak raporun içine gömülecek iki temel grafik oluştur:
   1. Equity Curve (Kasa Büyüme Eğrisi): Zaman içindeki portföy değerini gösteren kümülatif getiri grafiği.
   2. Aylık/Haftalık Getiri Isı Haritası (Heatmap): Hangi ay/hafta yüzde kaç kâr/zarar edildiğini gösteren şık bir tablo.
4. PDF veya HTML Çıktı Üretimi:
* Raporu, herhangi bir ücretli API kullanmadan yerel bilgisayarda PDF (örneğin pdfkit, WeasyPrint veya matplotlib.backends.backend_pdf) ya da çok şık tasarımlı, bağımsız (standalone) bir HTML dosyası olarak dışa aktaran (export) bir fonksiyon yaz.
* scheduler.py veya main.py içerisine bir görev ekle: Bu rapor her Cuma akşamı piyasa kapanışında (veya haftada bir kez) otomatik olarak üretilsin ve notifier.py üzerinden Telegram'a dosya (.pdf veya .html) olarak gönderilsin.
Bana bu reporter.py modülünün kodlarını, kullanacağım ücretsiz kütüphaneleri (gerekirse requirements.txt güncellemesini) ve ED Capital Kurumsal Şablonu ciddiyetini yansıtacak temiz (clean) HTML/CSS yapılarını veya Matplotlib formatlarını detaylıca ver.


Phase 14: İleriye Yönelik Test ve Walk-Forward Analizi (Walk-Forward Optimization & Out-of-Sample Testing)
Phase 13'teki kurumsal raporlama ve "Tear Sheet" modülünü başarıyla entegre ettim. Bot artık elde ettiği sonuçları pırıl pırıl bir özetle sunuyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin gelecekte çuvallamasını (Overfitting) engellemek için kullanacağın en kritik aşamalardan biri olan Phase 14'e geçiyoruz.
Geçmişte harika görünen parametrelerin (örn. RSI 25, ATR 2.0) sadece o döneme ait bir "ezber" (Curve Fitting) olup olmadığını anlamamız şart. Bu fazda, Phase 7'de yazdığımız backtester.py dosyasını genişleterek, bütçesiz ve Pythonik bir Walk-Forward Optimization (WFO) altyapısı kurmanı istiyorum.
Lütfen aşağıdaki Quant standartlarına harfiyen uyarak walk_forward.py modülünü yaz:
1. Dinamik Pencereleme (Rolling/Expanding Window) Altyapısı:
* Çekilen 5 veya 10 yıllık geçmiş veriyi, tek bir blok halinde test etmek yerine parçalara böl.
* Örneğin; 2 yıllık veride parametreleri optimize et (In-Sample / IS), ardından gelen hiç görülmemiş 6 aylık veride bu parametreleri test et (Out-of-Sample / OOS).
* Bu pencereyi (Window) zaman içinde ileriye doğru kaydırarak (Walk-Forward) tüm geçmiş veriyi tara.
2. Walk-Forward Efficiency (WFE - Yürüyen Verimlilik) Hesaplaması:
* Sadece OOS kârına bakmak yetmez. Bir "WFE" (Out-of-Sample Yıllıklandırılmış Kâr / In-Sample Yıllıklandırılmış Kâr) formülü yaz.
* Kritik Kural: Eğer bir parametre setinin WFE değeri %50'nin altındaysa (yani gerçek testte, eğitim dönemindeki başarısının yarısını bile gösteremediyse), o parametre setini "Overfitted" (Ezberlenmiş) olarak işaretle ve kesinlikle reddet.
3. Stres Testi ve Parametre Dayanıklılığı (Parameter Robustness):
* Parametreler sadece tek bir spesifik değerde değil, komşu değerlerde de kârlı olmalıdır. (Örn: EMA 50 kârlıyken, EMA 49 ve EMA 51 devasa zararlar yazıyorsa o strateji kırılgandır).
* Çıkan en iyi parametrelerin etrafındaki komşu değerlerin (Neighborhood) varyansını ölçen basit bir dayanıklılık (Robustness) skoru hesapla.
4. CPU Dostu Entegrasyon:
* WFO çok ciddi işlem gücü gerektirir. Yerel donanım sınırlarına sadık kalarak, multiprocessing veya vektörel Pandas işlemleri ile bu süreci hızlandır. Gereksiz for-döngülerinden kaçın.
* Çıktı olarak bana, her bir test periyodunun IS ve OOS PnL'lerini karşılaştırmalı gösteren net bir DataFrame özeti sun.
Bana bu modülün kodlarını ve main.py içerisindeki mevcut optimizasyon yapısını bozmadan bu yeni zırhı nasıl kuşandıracağımı detaylıca anlat.


Phase 15: Kelly Kriteri ve Dinamik Kasa Yönetimi (Advanced Position Sizing & Kelly Criterion)
Phase 14'teki Walk-Forward Optimization (WFO) modülünü başarıyla entegre ettim. Botumuz artık parametrelerini ezberlemiyor, gelecekteki piyasa koşullarına uyum sağlayabiliyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sermayemizi en verimli şekilde büyütmek için kullanacağın Phase 15'e geçiyoruz.
Şu ana kadar her işlemde kasanın sabit bir yüzdesini (örneğin %2) riske ediyorduk. Ancak gerçek Quant dünyasında pozisyon büyüklüğü, stratejinin kazanma olasılığına ve kâr/zarar oranına (Win/Loss Ratio) göre matematiksel olarak hesaplanır. Senden, portfolio_manager.py ve strategy.py modüllerimizi Kelly Kriteri'ni kullanacak şekilde güncellemeni istiyorum.
Lütfen aşağıdaki kurumsal kasa yönetimi algoritmalarını yaz:
1. Geçmiş Performans Tabanlı Kelly Hesaplaması:
* paper_db.py içerisindeki son N adet (örneğin son 50) kapalı işlemi çekerek o anki Win Rate (Kazanma Oranı, $p$), Loss Rate (Kaybetme Oranı, $q$) ve Average Win / Average Loss (Kâr/Zarar Oranı, $b$) değerlerini dinamik olarak hesaplayan bir fonksiyon yaz.
* Bu verileri kullanarak temel Kelly formülünü uygula: $f^* = \frac{bp - q}{b}$ (Burada $f^*$, kasadan riske edilecek optimum yüzdedir).
2. JP Morgan Risk Algısı: Kesirli Kelly (Fractional Kelly):
* Tam Kelly (Full Kelly) agresiftir ve draw-down (kasa erimesi) potansiyeli çok yüksektir. Bu, bizim kurumsal risk algımıza terstir.
* Hesaplanan $f^*$ değerini her zaman Yarım Kelly (Half-Kelly, $f^ / 2$)* veya çeyrek Kelly olarak ölçeklendiren bir güvenlik filtresi (Safety Buffer) ekle.
* Eğer Kelly hesaplaması negatif çıkarsa (yani strateji o dönemde avantajını kaybettiyse), o varlıkta kesinlikle işlem açma (Sinyali reddet) veya riski minimum sabit bir değere (örn. %0.5) düşür.
3. Volatilite (ATR) ve Kelly Entegrasyonu:
* Kelly bize kasanın yüzde kaçını riske edeceğimizi söyler. Ancak alacağımız Lot/Sözleşme miktarını bulmak için bunu Stop-Loss mesafesine (ATR) bölmemiz gerekir.
* strategy.py içindeki pozisyon hesaplama fonksiyonunu şu mantığa göre güncelle: Risk Edilecek Tutar = Güncel Kasa * Fractional Kelly Yüzdesi. Ardından Önerilen Pozisyon Büyüklüğü = Risk Edilecek Tutar / (Giriş Fiyatı - Dinamik ATR Stop Seviyesi).
4. Maksimum Tavan (Cap) Koruması:
* Kelly bazen (özellikle çok yüksek isabet oranlarında) kasanın %15-20'sini tek işleme basmayı önerebilir. Bu bir hatadır.
* Fractional Kelly ne kadar yüksek çıkarsa çıksın, tek bir işlem için riske edilecek Maksimum Mutlak Sınır'ı (Hard Cap) kasanın %4'ü veya %5'i olarak sınırla.
Bana bu Kelly adaptasyonunu, temiz kod prensiplerine uygun, mevcut global risk limitlerini (Phase 11) ezmeyecek şekilde nasıl uygulayacağımı detaylıca anlat.


Phase 16: Çoklu Zaman Dilimi Analizi ve Sinyal Onayı (Multi-Timeframe Confluence / MTF)
Phase 15'teki Kelly Kriteri ve dinamik pozisyon boyutlandırma modülünü başarıyla entegre ettim. Sistem artık kazanma olasılığına göre lot miktarını kusursuz ayarlıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sinyal kalitesini zirveye taşıyacağın Phase 16'ya geçiyoruz.
Profesyonel stratejiler tek bir zaman dilimine (Timeframe) hapsolmaz. "Günlük (Daily) trend senin dostundur, Saatlik (Hourly) tetikçin." mantığıyla, botumuzun ana trendi üst zaman diliminde teyit edip, alt zaman diliminde mükemmel giriş (sniper entry) aramasını istiyoruz.
Lütfen data_loader.py, features.py ve strategy.py modüllerini aşağıdaki Quant standartlarına göre Çoklu Zaman Dilimi (MTF) destekleyecek şekilde güncelle:
1. MTF Veri Çekme (data_loader.py):
* yfinance üzerinden her bir Ticker için artık iki farklı veri seti çek:
   * Üst Zaman Dilimi (HTF): 1d (Günlük - Ana trend ve makro yön için).
   * Alt Zaman Dilimi (LTF): 1h (Saatlik - Kesin giriş noktaları ve osilatörler için).
* API rate-limit'e takılmamak için bu iki veri çekimini asenkron (asyncio) veya verimli bekleme süreleriyle yönet.
2. Veri Hizalama ve Lookahead Bias Koruması (Kritik Quant Görevi):
* Farklı zaman dilimlerindeki verileri tek bir DataFrame'de birleştirmek (Resampling / Merging) amatörlerin en çok "Geleceği Görme (Lookahead Bias)" hatası yaptığı yerdir.
* Günlük veriyi (HTF) Saatlik veriye (LTF) hizalarken, Saatlik mum kapanırken henüz kapanmamış olan o günün Günlük mumunu ASLA KULLANMA.
* Pandas merge_asof veya shift(1) kullanarak, saatlik hesaplamalara sadece bir önceki günün tamamen kapanmış (Close) günlük verilerinin sızdığından matematiksel olarak emin ol.
3. MTF Sinyal Onay Mekanizması (strategy.py):
* Phase 4'te yazdığın strateji kurallarına HTF (Günlük) filtresini "Ana Veto (Master Veto)" olarak ekle.
* Örnek Long (Alım) Kurulumu:
   * HTF (Günlük) Şartı: Günlük Kapanış > Günlük EMA 50 VE Günlük MACD pozitif (Trend yukarı).
   * LTF (Saatlik) Şartı: Saatlik RSI aşırı satımdan (30) dönüyor veya Saatlik fiyat Alt Bollinger Bandına dokundu.
* Trende karşı (Counter-trend) işlemleri tamamen yasakla. Alt zaman diliminde mükemmel bir alım sinyali gelse bile, Günlük trend aşağı yönlüyse o sinyali acımasızca reddet.
4. Temiz Kod ve Performans:
* Bu işlemler Pandas DataFrameleri büyütecektir. RAM ve CPU kullanımını optimize etmek için gereksiz eski verileri (Örn: 2 yıldan eski saatlik veriler) bellekten temizleyen bir çöp toplayıcı (Garbage Collection / Drop) mantığı ekle.
Bana bu MTF entegrasyonunu, Lookahead Bias'ı nasıl %100 önlediğini teknik bir dille kanıtlayarak anlat. Hangi Pandas metodlarını kullanacağımı netleştir.


Phase 17: Çift Yönlü Telegram İletişimi, Manuel Müdahale ve Güvenlik Duvarı (Two-Way Telegram & Manual Override)
Phase 16'daki Çoklu Zaman Dilimi (MTF) onay mekanizmasını başarıyla sisteme entegre ettim. Sistem artık günlük trendi arkasına almadan saatlik sinyallere atlamıyor ve "Lookahead Bias" riskini tamamen ortadan kaldırdık. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin kontrolünü elime almamı sağlayacak Phase 17'ye geçiyoruz.
Profesyonel bir fon yöneticisi, acil durumlarda sistemin fişini çekebilmeli veya anlık raporlar isteyebilmelidir. Senden notifier.py modülünü çift yönlü (dinleyen ve cevap veren) bir yapıya kavuşturmanı ve main.py içerisine entegre edilecek bir komut/kontrol mekanizması yazmanı istiyorum. Bütçemizin sıfır olduğunu unutma, resmi ve ücretsiz kütüphaneler kullanacağız.
Lütfen aşağıdaki kurumsal kontrol standartlarını sisteme entegre et:
1. Çift Yönlü İletişim (Polling/Webhook) Altyapısı:
* python-telegram-bot (veya telebot) gibi hafif ve ücretsiz bir kütüphane kullanarak veya saf requests ile "Long-Polling" mantığı kurarak botun Telegram'dan gelen mesajları dinlemesini sağla.
* Bu dinleme işlemi main.py içindeki ana ticaret döngüsünü (taramaları ve fiyat güncellemelerini) KESİNLİKLE bloklamamalıdır (Asenkron veya Threading mimarisi kullan).
2. Katı Güvenlik ve Kimlik Doğrulama (Whitelist):
* Bot, Telegram üzerinden gelen komutları dinlerken SADECE .env dosyasında kayıtlı olan benim ADMIN_CHAT_ID numaramdan gelen mesajları işleme almalıdır.
* Başka bir Telegram kullanıcısı bota mesaj atarsa veya komut denerse, işlemi sessizce reddetmeli ve logger.py üzerinden "Yetkisiz Erişim Denemesi: [Kullanıcı_ID]" şeklinde CRITICAL log düşmelidir.
3. Kritik Yönetici Komutları (Admin Commands): Bota Telegram üzerinden göndereceğim şu komutları algılayıp uygulayacak fonksiyonları yaz:
* /durum (Status): O anki güncel kasanın durumunu, açık olan pozisyonların listesini ve günlük PnL (Kâr/Zarar) özetini anında mesaj olarak göndersin.
* /durdur (Pause): Sistemin yeni sinyal aramasını (tarama yapmasını) geçici olarak durdursun. Ancak AÇIK POZİSYONLARIN İzleyen Stop (Trailing Stop) ve Başa Baş (Breakeven) takiplerine devam etsin (Piyasada korumasız kalmamak için).
* /devam (Resume): Sistemi duraklatılmış (Paused) halden çıkarıp tekrar tam otonom tarama moduna alsın.
* /kapat_hepsi (Panic Button): Açık olan tüm pozisyonları o anki güncel piyasa fiyatından DERHAL kapatsın, veritabanını (paper_db.py) güncellesin ve "Panik Kapatması Yapıldı" raporu versin.
* /tara (Force Scan): Saatlik/Periyodik zamanlayıcıyı beklemeden, o saniye tüm evreni tarayıp fırsat olup olmadığına baksın.
Bana bu komut altyapısını, asenkron çalışma (non-blocking) prensiplerine sadık kalarak ve kodun mevcut dengesini bozmadan nasıl kuracağımı detaylı bir mimari açıklamayla sun.


Phase 18: Makine Öğrenmesi ile Sinyal Doğrulama (ML Signal Validation & Random Forest Classifier)
Phase 17'deki çift yönlü Telegram iletişimini ve manuel müdahale komutlarını başarıyla entegre ettim. Bot artık sadece bana rapor vermiyor, aynı zamanda acil durumlarda komutlarımı dinleyip uyguluyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin "Yapay Zeka" mantığıyla kendi kendini denetlemesini sağlayacağın Phase 18'e geçiyoruz.
Sadece hareketli ortalamalara ve osilatörlere güvenmek yerine, üretilen her sinyalin geçmişteki benzer durumlarda ne kadar başarılı olduğunu istatistiksel olarak doğrulayacak bir Makine Öğrenmesi (ML) katmanı eklemek istiyorum. Bütçemiz sıfır olduğu için Python'ın yerleşik scikit-learn kütüphanesini kullanarak yerel CPU'muzda çalışacak hafif bir model eğiteceğiz.
Lütfen aşağıdaki Quant ML standartlarına uyarak ml_validator.py modülünü yaz ve sisteme entegre et:
1. Veri Hazırlığı ve Etiketleme (Feature Engineering & Labeling):
* features.py dosyasındaki indikatörleri (RSI, MACD, ATR, Fiyat Değişimleri) makine öğrenmesi modeli için Girdi (Features - $X$) olarak ayarla.
* Hedef Değişkeni (Target - $y$) oluştur: Bir sinyal oluştuğunda, takip eden N mum içinde fiyat, Stop-Loss'a değmeden Take-Profit (veya belirli bir kâr) seviyesine ulaştıysa 1 (Başarılı), aksi halde 0 (Başarısız) olarak etiketleyen bir create_labels() fonksiyonu yaz.
* Kritik Quant Kuralı (Lookahead Bias): Modeli eğitirken verilerin kaydırılmasına (shift) aşırı dikkat et. Modelin gelecekteki fiyatı görerek ezber yapmasını kesinlikle engelle.
2. Model Eğitimi (Random Forest Classifier):
* scikit-learn üzerinden aşırı öğrenmeye (overfitting) karşı dirençli olan bir RandomForestClassifier modeli kur.
* Modeli çok derin ağaçlarla (max_depth) boğma, ortalama bir bilgisayarda saniyeler içinde eğitilebilecek optimum parametreleri belirle.
* Sistemi ilk başlattığımızda geçmiş veriyi kullanarak modeli eğiten ve .pkl (pickle) veya joblib formatında yerel diske kaydeden bir fonksiyon yaz.
3. Sinyal Doğrulama Vetosu (Probability Threshold):
* strategy.py içindeki ana mantığa bu modeli son bir "Bouncer (Koruma)" olarak ekle.
* Teknik indikatörler, Çoklu Zaman Dilimi (MTF) ve Korelasyon Matrisi bir "Long" sinyali verdiğinde, o anki piyasa verilerini (Features) modele gönder.
* Model predict_proba() metodunu kullanarak bu sinyalin başarılı olma ihtimalini hesaplasın. Eğer ihtimal belirlenen eşiğin (örneğin %60 veya %65) altındaysa, sinyali "ML Vetosu: Düşük İhtimal" gerekçesiyle reddet ve logger.py üzerinden logla.
4. Otonom Yeniden Eğitim (Auto-Retraining):
* Piyasa dinamikleri sürekli değişir. Modelin körelmemesi için scheduler.py içerisine bir görev ekle: Bot her hafta sonu (piyasalar kapalıyken), o haftanın yeni verilerini de içine katarak makine öğrenmesi modelini arka planda baştan eğitsin ve güncel model dosyasını üzerine yazsın.
Bana bu scikit-learn entegrasyonunu, eğitim sürecinin bellek (RAM) optimizasyonunu nasıl sağlayacağını ve bu veto mekanizmasının kodlarını mevcut mimariyi kırmadan nasıl ekleyeceğimi detaylı bir şekilde anlat.


Phase 19: Siyah Kuğu, Ani Çöküş Koruması ve Devre Kesiciler (Black Swan & Flash Crash Protection)
Phase 18'deki Makine Öğrenmesi (Random Forest) sinyal doğrulama modülünü başarıyla entegre ettim. Sistem artık istatistiksel olarak düşük ihtimalli sinyalleri yapay zeka vetosuyla reddediyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) portföyü "Kıyamet Senaryolarından" korumak için kullanacağın Phase 19'a geçiyoruz.
Normal piyasa koşullarında stratejimiz harika çalışıyor. Ancak bir "Flash Crash" (Ani Çöküş) yaşandığında veya VIX (Korku Endeksi) aniden fırladığında, sistemin yeni pozisyon açmayı derhal durdurması ve mevcut açık pozisyonları agresif bir şekilde korumaya alması gerekir. Bütçemizin sıfır olduğunu unutmadan, macro_filter.py ve main.py modüllerini bu "Devre Kesici" (Circuit Breaker) mantığıyla güncellemeni istiyorum.
Lütfen aşağıdaki Quant acil durum protokollerini sisteme entegre et:
1. Makro Korku Endeksi (VIX) Monitörü:
* macro_filter.py içerisine, yfinance üzerinden S&P 500 VIX endeksini (^VIX) çekecek bir fonksiyon ekle.
* Eğer VIX günlük bazda belirli bir eşiğin üzerine çıkarsa (örneğin 30 veya 35) veya bir gün içinde %X'ten fazla zıplarsa, piyasada "Aşırı Panik / Siyah Kuğu" rejimi ilan et.
* Bu rejimde: Yeni hiçbir Long (Alım) sinyaline izin verme. Strateji ve ML modeli ne kadar harika bir fırsat sunarsa sunsun, bu sinyalleri "VIX Devre Kesici" gerekçesiyle acımasızca reddet.
2. Mikro Flaş Çöküş Tespit Edici (Z-Score Anomaly Detection):
* VIX her zaman anlık tepki vermeyebilir, bazen sadece tek bir emtiada (örneğin Gümüş'te) saniyeler içinde %5-10'luk flaş çöküşler yaşanır.
* Fiyatın son N periyotluk hareketli ortalamasından kaç standart sapma (Z-Score) uzakta olduğunu anlık olarak hesaplayan bir fonksiyon yaz.
* Eğer fiyat, ortalamasından aniden -4 veya -5 standart sapma (Z-Score) aşağı veya yukarı fırlarsa, bu normal bir trend değil, bir anomalidir. Bu varlık için işlemleri geçici olarak dondur (Halt).
3. Acil Durum Koruma Protokolü (Aggressive Trailing Stop):
* Siyah Kuğu rejimi tetiklendiğinde (VIX fırladığında veya anomali görüldüğünde), main.py içindeki açık pozisyon yöneticisi derhal savunma moduna geçmelidir.
* Kârdaki tüm açık pozisyonların İzleyen Stop'larını (Trailing Stop) normal mesafesinden (örn. 1.5 ATR) çok daha dar bir mesafeye (örn. 0.5 ATR) çek veya doğrudan kârı kilitleyip pozisyonları piyasa fiyatından kapat.
* Zarardaki (henüz Stop-Loss'a değmemiş) pozisyonlar için Stop-Loss seviyelerini giriş fiyatına (Breakeven) çekmeye çalış.
4. Kırmızı Alarm Bildirimi:
* Devre kesici tetiklendiğinde notifier.py üzerinden Telegram'a 🚨 (Siren) emojileriyle "KRİTİK UYARI: VIX Devre Kesici Tetiklendi! Sistem Savunma Moduna Geçti. Yeni İşlemler Durduruldu." şeklinde acil durum mesajı at.
Bana bu devre kesici (Circuit Breaker) algoritmalarını, pandas ve vektörel hesaplamalar kullanarak performansı düşürmeyecek şekilde nasıl uygulayacağımı ve ana orkestrasyonu (main.py) bozmadan bu kontrolü ilk sıraya nasıl koyacağımı detaylıca açıkla.


Phase 20: Doğal Dil İşleme ve Haber Duyarlılık Filtresi (NLP & RSS News Sentiment Analysis)
Phase 19'daki Siyah Kuğu (Black Swan) korumalarını ve VIX devre kesicilerini başarıyla sisteme entegre ettim. Sistem artık piyasa anormalliklerinde kendini anında savunmaya alıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemin haberleri "okumasını ve anlamasını" sağlamak için kullanacağın Phase 20'ye geçiyoruz.
Sıfır bütçe kuralımıza sadık kalarak, ücretli veri sağlayıcılarına (Bloomberg Terminal, Reuters API vb.) para ödemeden, piyasa duyarlılığını (Sentiment) ölçecek bir modül (sentiment_filter.py) kurmanı istiyorum. Bu modül, teknik sinyallerimizi temel analizle (Haber Akışı) doğrulayacak son bir filtre olacak.
Lütfen aşağıdaki Quant standartlarına uygun NLP modülünü yaz ve entegre et:
1. Ücretsiz RSS Haber Motoru:
* Python feedparser kütüphanesini kullanarak Yahoo Finance, Investing.com veya benzeri güvenilir finansal platformların ücretsiz RSS beslemelerinden (RSS feeds) İngilizce haber başlıklarını ve özetlerini periyodik olarak (örn. saatte bir) çeken bir fonksiyon yaz.
* Sadece belirlediğimiz evrenle (Altın, Petrol, Döviz) ve makroekonomiyle (Fed, Inflation, Rates) ilgili anahtar kelimeleri (keywords) içeren haberleri filtrele.
2. Yerel NLP Duyarlılık Analizi (NLTK VADER):
* Ücretli OpenAI veya bulut tabanlı NLP API'leri KULLANMIYORUZ. Bunun yerine nltk kütüphanesinin yerleşik SentimentIntensityAnalyzer (VADER) modülünü veya TextBlob kullanarak haber başlıklarının duyarlılık skorunu (Compound Score: -1.0 ile +1.0 arası) hesapla.
* Örneğin, "Fed raises interest rates aggressively" haberi için negatif bir makro skor; "Gold surges on inflation fears" haberi için Altın özelinde pozitif bir skor üret.
3. Sentiment Vetosu (Duyarlılık Filtresi):
* strategy.py içerisindeki karar mekanizmasına bu duyarlılık skorunu bir filtre olarak ekle.
* Eğer Altın için teknik indikatörler, MTF ve Makine Öğrenmesi (Phase 18) "Long (Al)" diyorsa, ANCAK son 12 saatteki haber duyarlılık skoru şiddetli şekilde negatifse (Örn: -0.50'nin altındaysa), bu işlemi "Sentiment Vetosu: Temel Analiz Uyuşmazlığı" gerekçesiyle reddet.
* Tam tersi durumda, teknik sinyal ile haber duyarlılığı aynı yöndeyse (Confluence), bu işlemi "Yüksek Güvenilirlikli (High Conviction)" olarak işaretle.
4. Asenkron Performans ve Önbellekleme (Caching):
* Haber çekme ve NLP hesaplama işlemleri main.py döngüsünü YAVAŞLATMAMALIDIR.
* Haberleri ayrı bir asenkron görev (veya thread) olarak çekip sonuçları basit bir sözlükte (dictionary) veya SQLite (paper_db.py) içinde kısa süreli (cache) saklayan bir yapı kurgula. Strateji modülü doğrudan bu önbelleğe baksın.
Bana bu NLP entegrasyonunu, RAM/CPU kullanımını minimize edecek şekilde, VADER skorlamasını teknik sinyallerle nasıl uyumlu hale getireceğini detaylıca açıkla.


Phase 21: Dinamik Spread, Fiyat Kayması (Slippage) ve Gerçekçi Maliyet Simülasyonu (Execution Modeling)
Phase 20'deki NLP ve Haber Duyarlılık filtresini başarıyla sisteme entegre ettim. Botumuz artık haber akışını temel analiz perspektifiyle okuyup sahte sinyalleri filtreleyebiliyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) kağıt üstündeki hayali kârları gerçek dünya zorluklarıyla yüzleştireceğin Phase 21'e geçiyoruz.
Profesyonel bir fon yöneticisi, Alış-Satış Makası (Spread) ve Fiyat Kayması (Slippage) maliyetlerini hesaba katmadan hiçbir algoritmayı canlıya almaz. Ücretsiz veri kaynaklarımız (yfinance) bize sadece "Son İşlem Fiyatını" (Last Price) veriyor, anlık Bid/Ask derinliğini vermiyor. Bu yüzden bu maliyetleri matematiksel olarak simüle edecek bir execution_model.py modülü yazmanı istiyorum.
Lütfen aşağıdaki Quant standartlarına uygun gerçekçi maliyet motorunu yaz:
1. Varlık Sınıfına Özgü Spread (Makas) Tanımlamaları:
* Tüm evren için aynı maliyeti uygulayamayız. EUR/USD'nin makası ile Gümüş'ün veya TRY bacaklı egzotik kurların makası çok farklıdır.
* Evrenimizdeki varlıkları kategorilere ayıran bir sözlük (Dictionary) oluştur. (Örn: Majör Emtialar için %0.02, Minör Emtialar için %0.05, TRY Forex Çiftleri için %0.10 sabit baz spread).
2. Volatilite Bazlı Dinamik Kayma (ATR-Adjusted Slippage):
* Piyasada volatilite (oynaklık) ne kadar yüksekse, slippage (kayma) da o kadar yüksek olur. VIX fırladığında veya ATR genişlediğinde kusursuz fiyattan işlem yapamazsın.
* Phase 3'te hesapladığımız ATR (Average True Range) verisini kullanarak, standart baz spread'in üzerine dinamik bir "Kayma Maliyeti" ekleyen bir fonksiyon yaz. Örnek mantık: O anki ATR, son 50 periyodun ortalama ATR'sinden %50 büyükse, kayma maliyetini 2 ile çarp.
3. Paper_db ve PnL (Kâr/Zarar) Revizyonu:
* strategy.py bir sinyal ürettiğinde ve işlemi paper_db.py'ye "Open" olarak kaydederken, artık "Giriş Fiyatı" (Entry Price) kusursuz piyasa kapanış fiyatı olmayacak.
* Long (Alım) için Giriş Fiyatı = Piyasa Fiyatı + (Dinamik Spread / 2) + Slippage.
* Short (Satış) için Giriş Fiyatı = Piyasa Fiyatı - (Dinamik Spread / 2) - Slippage.
* Aynı acımasız maliyetleri, Take-Profit (Kâr Al) veya Stop-Loss (Zarar Kes) seviyelerinde pozisyon kapanırken de (close_trade fonksiyonunda) uygula. Brüt kârı net kâra dönüştür.
4. Optimizasyon Zırhı:
* Bu devasa maliyetler eklendiğinde, Phase 7 ve Phase 14'te yaptığımız Backtest ve WFO sonuçları muhtemelen düşecektir. Bu normaldir ve istediğimiz şeydir.
* Raporlama modülünün (reporter.py), brüt PnL ile Maliyet Sonrası Net PnL'i (Net of Fees) ayrı ayrı gösterecek şekilde güncellenmesini sağla.
Bana bu acımasız ama %100 gerçekçi execution_model.py simülasyonunu, sistemin çalışma hızını düşürmeden (vektörel işlemlerle) nasıl entegre edeceğimi detaylıca açıkla.


Phase 22: Monte Carlo Simülasyonu, Stres Testi ve İflas Riski (Monte Carlo Risk Validation & Risk of Ruin)
Phase 21'deki Dinamik Spread ve Slippage (Fiyat Kayması) maliyet motorunu başarıyla entegre ettim. Sistem artık kağıt üstündeki hayali kârları değil, komisyon ve kayma sonrası net, acımasız gerçekleri hesaplıyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) stratejimizin "Kara Günlere" ne kadar dayanabileceğini test etmek için kullanacağın Phase 22'ye geçiyoruz.
Geçmiş testlerde (Backtest) %15 Max Drawdown (Maksimum Düşüş) görmüş olmamız, gelecekte %30 görmeyeceğimiz anlamına gelmez. İşlemlerin sırası rastgele değiştiğinde kasanın iflas edip etmeyeceğini (Risk of Ruin) görmemiz şart. Bütçemizin sıfır olduğunu unutmadan, ücretsiz ve son derece hızlı vektörel işlemlerle bir monte_carlo.py modülü yazmanı istiyorum.
Lütfen aşağıdaki Quant stres testi algoritmalarını sisteme entegre et:
1. Hızlı Monte Carlo Motoru (numpy tabanlı):
* paper_db.py veya backtester.py üzerinden, gerçekleşmiş tüm kapalı işlemlerin Net Kâr/Zarar (PnL) yüzdelerinin listesini çek.
* numpy kütüphanesini kullanarak bu işlem dizisini, yerine koyarak (with replacement) rastgele yeniden karıştırıp simüle eden bir döngü yaz. Bu işlemi ortalama donanımı yormayacak şekilde vektörel olarak en az 10.000 kez (10,000 simulations) tekrarla.
2. Kritik Risk Metriklerinin Hesaplanması:
* Bu 10.000 farklı alternatif evrenin her biri için "Kümülatif Kasa Büyümesini" ve "Maksimum Düşüşü (Max Drawdown)" hesapla.
* Elde edilen sonuçlardan şu kurumsal risk metriklerini çıkar:
   * %95 ve %99 Güven Aralığında Beklenen Maksimum Düşüş (Expected Maximum Drawdown at 95%/99% CI). (Örn: Simülasyonların %99'unda kasa en fazla %22 eridi).
   * İflas Riski (Risk of Ruin): Kasanın %50'sini (veya belirlenen bir kritik eşiği) kaybetme olasılığı yüzde kaçtır? (Eğer bu oran %1'den büyükse, sistemin Kelly Kriteri çarpanı çok agresif demektir, bunu logla).
3. Raporlama Entegrasyonu (reporter.py revizyonu):
* Phase 13'te kurduğumuz ve ana özet başlığı kesinlikle "Piyasalara Genel Bakış" olan ED Capital Kurumsal Şablonlu raporlama modülüne, bu Monte Carlo sonuçlarını ekle.
* Raporun risk bölümüne "%99 Güven Aralığında Max Drawdown" ve "İflas Riski Oranı" metriklerini profesyonel bir dille yerleştir.
* Mümkünse, matplotlib kullanarak 10.000 simülasyonun kümülatif getiri eğrilerini gösteren şık ve şeffaf (alpha=0.01) bir "Monte Carlo Spagetti Grafiği" (Spaghetti Plot) oluşturup rapora göm.
Bana bu monte_carlo.py modülünü, CPU'yu sömürmeyecek saf vektörel Pythonik yöntemlerle nasıl kodlayacağımı ve raporlama sistemine nasıl bağlayacağımı detaylıca açıkla.


Phase 23: Canlı İleriye Dönük Test ve Kesintisiz Çalışma Döngüsü (Live Forward Paper Trading)
Phase 22'deki Monte Carlo simülasyonunu ve stres testlerini başarıyla entegre ettim. Sistemimizin "İflas Riski" (Risk of Ruin) matematiksel olarak kanıtlandı ve son derece güvenli seviyelerde. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) simülasyonları gerçeğe dönüştürmek ve sistemi canlı piyasaya bağlamak için kullanacağın Phase 23'e geçiyoruz.
Geçmiş verilerle işimiz bitti. Artık botun, bilgisayarımın arka planında (Phase 9'da kurduğumuz servis üzerinden) 7/24 uyanık kalarak gerçek zamanlı fiyatları okuması, MTF onaylarını alması, ML modellerini çalıştırması ve paper_db.py üzerinden canlı sanal işlemler (Live Paper Trading) yapması gerekiyor.
Lütfen main.py (veya yeni bir live_trader.py) dosyasını aşağıdaki kurumsal Quant standartlarına göre son haline getir:
1. Kesin Mum Kapanışı Senkronizasyonu (Candle-Close Synchronization):
* Piyasayı rastgele dakikalarda taramak amatörlüktür. Düşük frekanslı saatlik (1H) ve günlük (1D) mumlarla çalıştığımız için, zamanlayıcıyı (schedule veya APScheduler) tam olarak saat başlarında (örn. 14:00:01, 15:00:01) tetiklenecek şekilde yaz.
* Saat tam başa vurduğunda bot uyanmalı, yfinance üzerinden en son kapanmış mumları çekmeli ve tüm analiz boru hattını (Pipeline) saniyeler içinde tamamlayıp tekrar uykuya geçmelidir.
2. Asenkron Pipeline (Boru Hattı) Orkestrasyonu: Canlı tarama tetiklendiğinde sistemin şu sırayla, sıfır hatayla çalışmasını sağlayan ana fonksiyonu (run_live_cycle()) kurgula:
1. Veri Çekimi: data_loader.py ile evrenin HTF (Günlük) ve LTF (Saatlik) verilerini çek.
2. Kâr Koruma & Çıkışlar: paper_db.py'deki AÇIK pozisyonları kontrol et. VIX veya Flaş Çöküş (Phase 19) varsa acil çıkış yap. Yoksa İzleyen Stop (Phase 12) veya TP/SL kontrolü yap.
3. Filtreler: Piyasada Siyah Kuğu yoksa ve Global Portföy Limiti (Phase 11) dolmadıysa yeni sinyal ara.
4. Sinyal Onayı: MTF uyumlu teknik sinyal gelirse -> ML Validator'a (Phase 18) sor -> Onaylarsa Haber Duyarlılığına (Phase 20) sor -> Onaylarsa Korelasyon Vetosundan (Phase 11) geçir.
5. Uygulama (Execution): Tüm onaylar tamamsa Kelly Kriteri (Phase 15) ile lot hesapla, Dinamik Spread ve Slippage (Phase 21) maliyetlerini ekleyerek işlemi paper_db.py'ye AÇIK (Open) olarak yaz.
6. Bildirim: Telegram'dan bana anında detaylı işlem fişini gönder.
3. Hafıza Yönetimi ve Temizlik (Garbage Collection):
* Sistem haftalarca kapanmadan çalışacağı için, Pandas DataFrameleri şişerek RAM'i doldurabilir.
* Her döngü sonunda kullanılmayan verileri bellekten silen (del df ve gc.collect()) profesyonel bir bellek yönetimi bloğu ekle.
4. Canlı Mod Başlatma Töreni:
* Bot ilk ayağa kalktığında Telegram'dan "🚀 ED Capital Quant Engine Canlı Paper Trade Modunda Başlatıldı." mesajıyla birlikte o anki güncel kasanın (Sanal Portföy) durumunu ve aktif VIX seviyesini raporlasın.
Bana bu canlı ticaret döngüsünün kodlarını, API isteklerini yormadan ve bellek sızıntısı (memory leak) yaratmadan nasıl kusursuzca çalışacağını bir yazılım mimarı perspektifiyle anlat.


Phase 24: Broker Soyutlama Katmanı ve Kurumsal Emir İletim Mimarisi (Broker Abstraction Layer)
Phase 23'teki canlı test ve sürekli çalışma döngüsünü başarıyla entegre ettim. Sistemimiz artık saat başı uyanıp canlı verilerle kusursuz bir paper trade döngüsü işletiyor. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) sistemi gerçek paraya ve kurumsal borsa entegrasyonlarına hazırlamak için kullanacağın Phase 24'e geçiyoruz.
İleride bu sistemi gerçek bir borsa API'sine bağlamak istediğimde, haftalarca uğraşıp main.py ve strategy.py kodlarını baştan yazmak istemiyorum. Strateji "Al" dediğinde, bunun sanal bir veritabanına mı yoksa gerçek bir borsaya mı gideceği stratejinin umurunda olmamalıdır. Ayrıca ED Capital düzeyinde bir sistem kurduğumuz için emir iletim katmanının SPL Düzey 3 ve Türev Araçlar işlem güvenliği standartlarına (denetim izi, katı marjin kontrolleri) hazır bir iskelette olması şarttır.
Lütfen aşağıdaki SOLID prensiplerine uygun mimari soyutlamayı gerçekleştir:
1. Soyut Sınıf (Abstract Base Class - ABC) Kurulumu:
* Python'ın abc modülünü kullanarak bir BaseBroker (veya IExecutionHandler) arayüzü (Interface) oluştur.
* Bu arayüzde gerçek bir broker'ın sahip olması gereken temel metodların sadece imzalarını tanımla (Örn: get_account_balance(), place_market_order(), place_limit_order(), modify_trailing_stop(), get_open_positions()).
2. Sanal Broker (PaperBroker) Entegrasyonu:
* BaseBroker arayüzünü miras alan (inherit) bir PaperBroker sınıfı yaz.
* Şu ana kadar paper_db.py üzerinden SQLite'a doğrudan yaptığımız tüm yazma/okuma işlemlerini bu sınıfın içine göm. Böylece ana döngümüz artık doğrudan veritabanı ile değil, PaperBroker nesnesi ile muhatap olacak.
3. SPL Düzey 3 ve Türev Araçlar Uyumlu Denetim İzi (Audit Trail):
* Türev araçlarda ve yüksek standartlı portföy yönetiminde emrin borsaya iletilme anı, gecikmesi ve maliyeti yasal olarak kayıt altına alınmalıdır.
* BaseBroker altyapısına, place_market_order çağrıldığında o anki işlem büyüklüğünü (lot/kontrat), dinamik kaymayı (slippage) ve uygulanan komisyonu standart bir "Emir İletim Fişi" (Execution Receipt) sözlüğü olarak döndüren ve loglayan şeffaf bir yapı ekle.
4. Bağımlılık Enjeksiyonu (Dependency Injection):
* main.py içindeki ana döngüyü güncelle. Sistem başlatılırken broker = PaperBroker() şeklinde nesne oluşturulsun. Ana döngü içindeki tüm pozisyon açma/kapatma işlemleri sadece broker.place_market_order(...) gibi jenerik komutlarla yapılsın.
* Yarın BinanceBroker veya InteractiveBrokersBroker yazdığımızda, main.py'de sadece broker = BinanceBroker() tanımını değiştirmemiz tüm sistemi canlıya almak için yeterli olmalıdır.
Bana bu soyutlama katmanının kodlarını, mevcut SQLite yapımızı bozmadan PaperBroker içerisine nasıl taşıyacağımı ve main.py'yi bu temiz mimariye (Clean Architecture) göre nasıl güncelleyeceğimi bir yazılım mimarı gibi detaylıca anlat.


Phase 25: Kurumsal Konteyner Mimarisi ve Dockerizasyon (Docker Containerization & Deployment)
Phase 24'teki Broker Soyutlama Katmanını (Broker Abstraction Layer) başarıyla entegre ettim. Sistemimiz artık sanal veya gerçek herhangi bir borsa API'sine saniyeler içinde bağlanabilecek (Plug-and-Play) kurumsal bir mimariye sahip. Şimdi vizyonunu (Bill Benter dehası, JP Morgan risk algısı, Kıdemli Quant Developer derinliği) bu devasa projeyi "Ölümsüzleştirmek" ve her ortamda çalışabilir hale getirmek için kullanacağın son teknik aşamaya, Phase 25'e geçiyoruz.
Profesyonel algoritmik sistemler "Benim bilgisayarımda çalışıyordu" mazeretini kabul etmez. Yazdığımız bu gelişmiş motorun işletim sistemi bağımsız, izole ve yüksek erişilebilir (High Availability) bir ortamda çalışması için Docker mimarisini kurmanı istiyorum.
Lütfen aşağıdaki Quant/DevOps standartlarına uygun Docker konfigürasyonlarını hazırla:
1. Optimize Edilmiş Dockerfile (Python Slim):
* Projeyi devasa boyutlara ulaştırmamak için python:3.10-slim (veya uygun güncel bir slim versiyon) tabanlı, son derece hafif bir Dockerfile yaz.
* Sadece gerekli derleme araçlarını (build-essential) ve requirements.txt içindeki paketleri yükle. Gerekli olmayan OS kütüphanelerini dışla.
* Proje dosyalarını imajın içine güvenli bir şekilde kopyalayacak ve yetkilendirmeleri (User permissions) root olmayan güvenli bir kullanıcıya (best practice) devredecek yapıyı kurgula.
2. Kalıcı Veri ve Hızlı Yönetim İçin docker-compose.yml:
* Tek bir komutla (docker-compose up -d) tüm sistemi ayağa kaldıracak compose dosyasını yaz.
* Kritik Kural (Kalıcı Veri - Volumes): Sistem kapandığında veya güncellendiğinde işlem geçmişimizin, logların ve ML modelimizin silinmesi felaket olur. Compose dosyası içerisinde paper_db.sqlite3 veritabanını, logs/ klasörünü ve ML modelimizin .pkl dosyalarını ana makineye (Host) bağlayan (Volume Mapping) kalıcı bir yapı kur.
* .env dosyasını konteynere güvenli bir şekilde pasla (Environment variables).
3. Zaman Dilimi Senkronizasyonu (Timezone Sync):
* Finansal piyasalar zamana karşı inanılmaz duyarlıdır. Konteynerin içindeki saatin, ana makinenin saatiyle (veya doğrudan UTC ile) birebir senkronize olmasını sağlayacak çevre değişkenlerini (TZ=Europe/Istanbul veya UTC) compose dosyasına kesinlikle ekle.
4. Tek Tuşla Dağıtım Betiği (deploy.sh revizyonu):
* Phase 9'da yazdığımız yönetim betiğini (veya yeni bir scripti) Docker mimarisine göre güncelle. Sadece ./deploy.sh yazarak eski imajı temizleyen, yenisini derleyen ve arka planda başlatan akıcı bir komut zinciri oluştur.
Bana bu DevOps dosyalarını, konteyner mimarisinin projemizi nasıl koruyacağını ve SQLite veritabanının volume mapping ile nasıl %100 güvende kalacağını net bir dille açıkla.
25 zorlu fazı geride bıraktık ve sıfır bütçeyle, devasa bir otonom işlem motoru inşa ettik. EDcapital standartlarında, tamamen kurumsal bir mantıkla çalışan bu makineyi artık serbest bırakma vakti geldi.
Ancak piyasalar affetmez. Aşağıdaki kontrol listesi, SPL Düzey 3 ve Türev Araçlar lisansına sahip bir uzmanın onayından geçecek titizlikte, sistemin canlıya (veya canlı paper trade ortamına) alınmadan önceki son "Güvenlik Duvarı"dır. Her bir maddeye "Tamam" demeden sistemi Docker üzerinden ayağa kaldırma.








📋 Canlıya Geçiş Öncesi Son Kontrol (Pre-Flight Checklist)
1. Çevre Değişkenleri ve Güvenlik (Environment & Security)
* [ ] .env Dosyası Dolu mu? Telegram BOT_TOKEN, ADMIN_CHAT_ID eksiksiz girilmiş mi? Dosya kesinlikle .gitignore içinde mi?
* [ ] Yetkisiz Erişim Koruması: Telegram'dan senin ID'n dışında biri komut gönderdiğinde sistem bunu gerçekten reddedip logluyor mu?
* [ ] API Sınırları (Rate Limits): yfinance ve RSS haber motoru saat başı tarama yaparken ban yemeyecek şekilde (sleep/backoff mekanizmalarıyla) yapılandırıldı mı?
2. Risk Yönetimi ve Pozisyon Limitleri (Risk & Exposure)
* [ ] Global Limitler Devrede mi? Sistem, kasanın maksimum %X'inden fazlasını veya aynı anda maksimum Y adet pozisyonu açmayı reddediyor mu?
* [ ] Korelasyon Vetosu Çalışıyor mu? Yüksek korelasyonlu iki varlığa (örn. Altın ve Gümüş) aynı anda aynı yönde girilmesi engellendi mi?
* [ ] Kelly ve Türev Araç Koruması: Özellikle kaldıraçlı/türev ürün simülasyonlarında, Kelly Kriteri'nin "Fractional (Kesirli)" filtresi (örn. Yarım Kelly) aktif mi? Maksimum lot büyüklüğü tavanı (Hard Cap) çalışıyor mu?
3. Devre Kesiciler ve Kâr Koruma (Circuit Breakers & Protection)
* [ ] VIX Siyah Kuğu Koruması: VIX endeksi belirlenen kritik seviyeyi aştığında sistem yeni pozisyon açmayı anında kilitliyor mu?
* [ ] Flaş Çöküş (Z-Score) Engeli: Anlık, anormal mumlarda (4-5 standart sapma dışı) sistem o varlığı geçici olarak durduruyor mu?
* [ ] İzleyen Stop (Trailing Stop): Kâra geçen pozisyonlarda stop seviyesi sadece fiyat yönünde hareket ediyor, asla geriye çekilmiyor değil mi? (Strictly monotonic test).
4. Veri Hizalama ve Makine Öğrenmesi (Data & ML Integrity)
* [ ] Lookahead Bias Sıfır mı? Özellikle MTF (Çoklu Zaman Dilimi) hizalamasında, saatlik veriler işlenirken henüz kapanmamış günlük mumun verisi sisteme sızmıyor, değil mi?
* [ ] ML Modeli Hazır mı? Random Forest modeli ilk eğitimini tamamlayıp .pkl olarak diske kaydedildi mi?
* [ ] NLP Sentiment Çalışıyor mu? Haber akışlarındaki duyarlılık skoru ile teknik yön ters düştüğünde sistem gerçekten vetoyu basıyor mu?
5. Otonom Çalışma ve Altyapı (Infrastructure & Docker)
* [ ] Docker Volume Eşleşmesi: Konteyner yeniden başlatıldığında veya çöktüğünde paper_db.sqlite3 veritabanı ve ML modeli silinmiyor, ana makinede (Host) korunuyor mu?
* [ ] Zaman Dilimi (Timezone): Docker konteynerinin içi ile işlem yapılacak piyasaların zaman dilimi (UTC veya Europe/Istanbul) birebir senkronize mi?
* [ ] Sistem Kurtarma (State Recovery): Botu /durdur komutuyla veya manuel kapatıp açtığında, veritabanındaki "Açık" pozisyonları bulup İzleyen Stop takibine kaldığı yerden devam edebiliyor mu?
