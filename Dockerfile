FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && find /usr/local/lib/python*/site-packages/pyrlottie -type f \( -name 'lottie2gif' -o -name 'gif2webp' -o -name 'app' \) -exec chmod 0755 {} +

COPY . .

CMD ["python", "main.py"]
