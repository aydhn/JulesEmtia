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
RUN python -m nltk.downloader vader_lexicon -d /usr/share/nltk_data || true

COPY src/ ./src/
# Move main back out to app root based on structure if needed, or leave in src
# According to main.py path, it looks for src.* imports
# The main.py should be in /app/main.py

RUN mv /app/src/main.py /app/main.py 2>/dev/null || true

RUN chown -R quantuser:quantuser /app

USER quantuser

ENV PYTHONPATH=/app

CMD ["python", "main.py"]
