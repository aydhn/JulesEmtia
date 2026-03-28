FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends     build-essential gcc sqlite3 wkhtmltopdf && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd -m quantuser
RUN chown -R quantuser:quantuser /app
USER quantuser

COPY . .

RUN python -m nltk.downloader vader_lexicon

CMD ["python", "main.py"]
