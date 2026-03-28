FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including tzdata and wkhtmltopdf for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Set Timezone
ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create a non-root user for security
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser

# Run the engine
CMD ["python", "main.py"]
