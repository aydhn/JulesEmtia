FROM python:3.10-slim

# Install system dependencies (build-essential for numpy/pandas building if needed, sqlite3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc sqlite3 wkhtmltopdf && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN useradd -m quantuser
RUN chown -R quantuser:quantuser /app
USER quantuser

# Download NLP data explicitly during build
RUN python -m nltk.downloader vader_lexicon

COPY . .

CMD ["python", "main.py"]
