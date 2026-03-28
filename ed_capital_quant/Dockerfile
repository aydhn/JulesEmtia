FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Istanbul

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -r -u 1000 quantuser
RUN mkdir -p /app/logs /app/data_storage /app/reports && \
    chown -R quantuser:quantuser /app

# Switch to non-root user
USER quantuser

# Copy application code
COPY --chown=quantuser:quantuser . .

# Run the application
CMD ["python", "main.py"]
