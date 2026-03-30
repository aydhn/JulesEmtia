# Use slim python image to minimize size
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Istanbul

# Install system dependencies required for compilation and reporting
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Create necessary directories and set permissions for a non-root user
RUN mkdir -p /app/data /app/logs /app/models /app/reports && \
    useradd -m quantuser && \
    chown -R quantuser:quantuser /app

# Switch to non-root user for security
USER quantuser

# Command to run the bot
CMD ["python", "main.py"]
