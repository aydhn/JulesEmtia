# Base Image: Python 3.10 Slim (Minimal OS footprint)
FROM python:3.10-slim

# Maintainer and Labels
LABEL maintainer="ED Capital Quant Engineering"
LABEL description="Autonomous Multi-Timeframe Algorithmic Trading Engine"

# Environment Variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Europe/Istanbul

# Install OS dependencies (build tools for ML libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set Timezone
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create a non-root user for security (Best Practice)
RUN useradd -m -s /bin/bash quantuser

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Download NLTK data required for NLP module
RUN python -c "import nltk; nltk.download('vader_lexicon', download_dir='/usr/local/share/nltk_data')"

# Copy project files
COPY . .

# Set ownership to non-root user
RUN chown -R quantuser:quantuser /app

# Switch to non-root user
USER quantuser

# Command to run the engine
CMD ["python", "main.py"]
