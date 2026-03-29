# Phase 25: Dockerization (Python Slim)
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Istanbul

# Create app directory and set as working directory
WORKDIR /app

# Install system dependencies required for compilation and pdf generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wkhtmltopdf \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# NLTK Vader setup (run once during build)
RUN python -m nltk.downloader vader_lexicon

# Create non-root user and directories
RUN useradd -m quantuser && \
    mkdir -p /app/logs /app/models /app/reports && \
    chown -R quantuser:quantuser /app

# Copy the application code
COPY . .

# Ensure permissions
RUN chown -R quantuser:quantuser /app

# Switch to non-root user
USER quantuser

# Command to run the bot
CMD ["python", "main.py"]
