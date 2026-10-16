FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt

RUN python -m pip install --upgrade pip \
    && python -m pip install -r backend/requirements.txt

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY backend ./backend
COPY scripts ./scripts

RUN chmod +x ./scripts/start_backend.sh

EXPOSE 8000

CMD ["./scripts/start_backend.sh"]
