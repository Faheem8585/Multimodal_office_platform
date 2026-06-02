#!/usr/bin/env bash
# Container entrypoint for the API: apply migrations, optionally seed, then serve.
# Migrations run here (not at image build) so they hit the real DB at deploy time.
set -euo pipefail

echo "[entrypoint] running database migrations..."
alembic upgrade head

if [[ "${SEED_ON_START:-false}" == "true" ]]; then
  echo "[entrypoint] seeding initial data..."
  python -m app.initial_data || echo "[entrypoint] seed skipped/failed (non-fatal)"
fi

echo "[entrypoint] starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-4}"
