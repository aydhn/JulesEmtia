FROM python:3.10-slim

# Install necessary system dependencies for math/compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and non-root user
WORKDIR /app
RUN useradd -m quantuser && chown quantuser:quantuser /app

# Switch to non-root user
USER quantuser

# Copy requirements and install
COPY --chown=quantuser:quantuser requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK data (VADER lexicon)
RUN python -c "import nltk; nltk.download('vader_lexicon')"

# Copy the rest of the application
COPY --chown=quantuser:quantuser src/ src/
COPY --chown=quantuser:quantuser main.py .

# Create necessary directories for runtime
RUN mkdir -p data logs models reports

# Entrypoint
CMD ["python", "main.py"]
