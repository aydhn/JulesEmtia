# Dockerfile
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a secure, non-root user
RUN adduser --disabled-password --gecos '' quantuser

# Set working directory
WORKDIR /app

# Install build dependencies (often needed for TA-Lib or C-extensions, though we use pandas_ta)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY . .

# Ensure correct permissions for the non-root user
RUN mkdir -p /app/logs /app/models \
    && chown -R quantuser:quantuser /app

# Switch to the non-root user
USER quantuser

# Run the application
CMD ["python", "main.py"]
