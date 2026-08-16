#!/bin/sh
# Container startup: bring the schema up to date, then hand off to the CMD.
#
# Platforms like Render's free tier offer no shell and no pre-deploy hook, so
# migrations have to run here. `alembic upgrade head` is idempotent — on a
# healthy database it is a no-op after the first boot.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] running database migrations..."
    alembic upgrade head
    echo "[entrypoint] migrations up to date."
fi

# Demo/staging convenience only. Never enable against real data: the seed
# refuses to run when ENVIRONMENT=production, and --reset wipes demo rows.
if [ "${SEED_ON_START:-false}" = "true" ]; then
    echo "[entrypoint] seeding demo data..."
    python -m app.seed
fi

exec "$@"
