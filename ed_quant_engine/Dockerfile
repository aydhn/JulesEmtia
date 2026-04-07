FROM python:3.10-slim

# OS Gerekli Paketler ve Saat Dilimi
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Non-root Kullanıcı
RUN useradd -m quantuser

WORKDIR /app

# Dosya İzinleri ve Klasörler
RUN mkdir -p /app/data /app/models /app/logs /app/reports && \
    chown -R quantuser:quantuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK verisini indir
RUN python -m nltk.downloader vader_lexicon

COPY src/ ./src/
COPY main.py .

RUN chown -R quantuser:quantuser /app

USER quantuser

CMD ["python", "main.py"]
