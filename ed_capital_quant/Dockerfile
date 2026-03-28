FROM python:3.10-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli OS kütüphanelerini yükle (pdfkit için wkhtmltopdf dahil)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK verilerini indir
RUN python -m nltk.downloader vader_lexicon

# Proje dosyalarını kopyala
COPY . .

# Güvenli kullanıcı oluştur (root yetkisinden çık)
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser

# Sistemi başlat
CMD ["python", "main.py"]