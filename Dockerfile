FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PROCESSED_DATA_DIR=/app/data/processed \
    GUTENBERG_RAW_DIR=/app/data/raw/gutenberg \
    INTERACTION_LOG_PATH=/app/data/processed/interactions.jsonl \
    ACCOUNT_STORE_PATH=/app/data/processed/accounts.json

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY backend/pyproject.toml backend/README.md /app/backend/
COPY backend/app /app/backend/app
COPY scripts /app/scripts

RUN pip install --no-cache-dir -e /app/backend

RUN mkdir -p /app/data/processed /app/data/raw/gutenberg /app/data/uploads

WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
