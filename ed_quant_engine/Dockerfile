FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Europe/Istanbul

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/data /app/models /app/logs /app/reports

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x manage_bot.sh deploy.sh

# Best practice: run as non-root
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser

CMD ["python", "main.py"]
