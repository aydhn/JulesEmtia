# Phase 25: Corporate Container Architecture
FROM python:3.10-slim

# Prevent Python from writing pyc files and keep stdout unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for data processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up non-root user for security
RUN useradd -m -r -u 1000 quantuser
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set permissions for data, logs, and models
RUN chown -R quantuser:quantuser /app

# Switch to non-root user
USER quantuser

# Expose no ports as this is a background worker
# CMD defaults to running the main loop
CMD ["python", "main.py"]
