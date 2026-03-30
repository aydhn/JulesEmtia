FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y tzdata build-essential && rm -rf /var/lib/apt/lists/*
ENV TZ="Europe/Istanbul"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser
CMD ["python", "main.py"]
