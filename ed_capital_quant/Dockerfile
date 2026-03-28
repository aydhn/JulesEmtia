FROM python:3.10-slim

# Install OS dependencies for building ML and basic network tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY src/ ./src/

# Set timezone dynamically via build arg or compose
ENV TZ=Europe/Istanbul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Create directories for volumes
RUN mkdir -p logs models data reports

# Create a non-root user
RUN useradd -m quantuser && \
    chown -R quantuser:quantuser /app
USER quantuser

# Command to run the engine
CMD ["python", "-u", "src/main.py"]
