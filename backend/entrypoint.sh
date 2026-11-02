#!/bin/sh
set -e

echo "==> [TripWiser] Checking and applying database migrations (alembic upgrade head)..."
alembic upgrade head

PORT="${PORT:-8000}"
echo "==> [TripWiser] Starting FastAPI Uvicorn server on 0.0.0.0:${PORT}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT}"

