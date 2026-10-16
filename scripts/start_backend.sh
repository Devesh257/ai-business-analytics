#!/usr/bin/env bash

set -euo pipefail

: "${PORT:=8000}"

echo "Running database migrations..."
alembic upgrade head

echo "Starting Signal Ledger backend on port ${PORT}..."
exec python -m uvicorn app.main:app \
  --app-dir backend \
  --host 0.0.0.0 \
  --port "${PORT}"
