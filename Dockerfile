FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    APP_ENV=production \
    GENERATED_APPS_DIR=/data/apps \
    WEB_CONCURRENCY=1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY README.md ./README.md

RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /data/apps \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

VOLUME ["/data"]

CMD ["python", "-m", "app.server"]
