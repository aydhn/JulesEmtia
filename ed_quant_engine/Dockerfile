# Use slim image for minimal footprint
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV TZ=Europe/Istanbul

# Install dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create user
RUN useradd -m quantuser

WORKDIR /home/quantuser/app
COPY requirements.txt .

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data during build
RUN python -m nltk.downloader vader_lexicon

# Copy application code
COPY . .

# Set permissions
RUN chown -R quantuser:quantuser /home/quantuser/app
USER quantuser

CMD ["python", "main.py"]
