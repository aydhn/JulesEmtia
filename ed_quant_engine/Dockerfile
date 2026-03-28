# Phase 25: Corporate Dockerization
FROM python:3.10-slim

# Avoid writing .pyc files
ENV PYTHONDONTWRITEBYTECODE 1
# Unbuffered output for logs
ENV PYTHONUNBUFFERED 1
# Timezone Sync (Critical for Quant)
ENV TZ=Europe/Istanbul

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Non-root user for security
RUN useradd -m quantuser && chown -R quantuser:quantuser /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=quantuser:quantuser . .

# Run as non-root
USER quantuser

CMD ["python", "main.py"]
