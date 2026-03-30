# Base image: Use a slim version of Python to keep the container lightweight
FROM python:3.10-slim

# Set environment variables for non-interactive installations and timezone sync
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ="Europe/Istanbul"

# Install build dependencies for compiling certain Python packages (like pandas, scipy)
# and for generating PDFs (weasyprint) if needed.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK VADER lexicon during build to avoid downloading on every startup
RUN python -m nltk.downloader vader_lexicon

# Copy the rest of the application code
COPY . /app/

# Run as a non-root user for security (Best Practice)
RUN useradd -m quantuser && chown -R quantuser:quantuser /app
USER quantuser

# The command to start the bot
CMD ["python", "main.py"]
