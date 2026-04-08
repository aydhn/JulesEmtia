FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data (vader_lexicon)
RUN python -m nltk.downloader vader_lexicon

# Copy the rest of the application code
COPY . .

# Create directories for volumes
RUN mkdir -p /app/data /app/logs /app/models /app/reports

# Run the bot
CMD ["python", "main.py"]
