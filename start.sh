#!/bin/bash
set -e

echo "Starting PayFlow API..."
echo "Running database migrations..."
python -m alembic upgrade head
echo "Migrations complete."
echo "Starting server..."
exec python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT