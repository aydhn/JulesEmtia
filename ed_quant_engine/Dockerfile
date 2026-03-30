FROM python:3.10-slim
WORKDIR /app

# Install build dependencies for compiling pandas/numpy if needed
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user (Phase 25 Best Practice)
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser

COPY . .

CMD ["python", "main.py"]\n