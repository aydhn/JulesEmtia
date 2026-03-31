# Phase 25: Docker Containerization
# Uses a slim python image to minimize vulnerabilities and footprint
FROM python:3.10-slim

# Prevent Python from writing pyc files and buffer
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=Europe/Istanbul

# Install dependencies (build-essential for C extensions if needed by pandas/numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Ensure manage script is executable
RUN chmod +x manage_bot.sh

# Run the application
CMD ["python", "main.py"]
