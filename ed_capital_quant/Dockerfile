FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app
COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev \
    && pip install --upgrade pip \
    && pip install -r requirements.txt \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

RUN python -c "import nltk; nltk.download('vader_lexicon')"

COPY . .

RUN useradd -m -r -s /bin/bash ed_user
RUN chown -R ed_user:ed_user /app

USER ed_user
CMD ["python", "main.py"]
