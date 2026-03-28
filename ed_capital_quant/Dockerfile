FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r requirements.txt
RUN python -c "import nltk; nltk.download('vader_lexicon')"
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
ENV PYTHONPATH=/app
CMD ["python", "-m", "src.bot.main"]
