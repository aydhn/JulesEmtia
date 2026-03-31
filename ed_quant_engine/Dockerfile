FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Istanbul

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure NLTK data is downloaded
RUN python -m nltk.downloader vader_lexicon

COPY . .

RUN adduser --disabled-password --gecos "" quantuser && \
    chown -R quantuser:quantuser /app
USER quantuser

CMD ["python", "-m", "src.main_live"]
