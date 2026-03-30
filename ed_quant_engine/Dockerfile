# Phase 25: Corporate Container Architecture
FROM python:3.10-slim

# Install system dependencies (build-essential for compiling numpy/pandas C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create a non-root user (Best Practice)
RUN groupadd -r quant && useradd -r -g quant quant
RUN chown -R quant:quant /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NLTK Vader Lexicon pre-download to save container startup time
RUN python -c "import nltk; nltk.download('vader_lexicon')"

# Copy application files
COPY core/ ./core/
COPY main.py .

# Permissions
RUN chown -R quant:quant /app

# Switch to non-root user
USER quant

# Run the background loop
CMD ["python", "main.py"]
