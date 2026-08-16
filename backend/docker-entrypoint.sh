#!/bin/sh
# Container startup: bring the schema up to date, then hand off to the CMD.
#
# Platforms like Render's free tier offer no shell and no pre-deploy hook, so
# migrations have to run here. `alembic upgrade head` is idempotent — on a
# healthy database it is a no-op after the first boot.
set -e

# Preflight. Without this, a missing DATABASE_URL silently falls back to the
# development default and surfaces as a 40-line asyncpg traceback ending in
# "Connect call failed ('127.0.0.1', 5432)" — which reads like a database
# outage rather than an unset variable.
case "${DATABASE_URL:-}" in
    "")
        echo "[entrypoint] FATAL: DATABASE_URL is not set." >&2
        echo "[entrypoint] The app defaults to localhost:5432, and nothing is listening there" >&2
        echo "[entrypoint] inside this container. Set DATABASE_URL on the service to your" >&2
        echo "[entrypoint] managed Postgres connection string (on Render: the *Internal*" >&2
        echo "[entrypoint] Database URL). See docs/DEPLOYMENT.md." >&2
        exit 1
        ;;
    *@localhost[:/]*|*@127.0.0.1[:/]*|*@\[::1\][:/]*)
        # `--network host` against a Postgres on the host is a valid local
        # setup, so this is a guard rather than a prohibition.
        if [ "${ALLOW_LOCALHOST_DB:-false}" = "true" ]; then
            echo "[entrypoint] DATABASE_URL points at localhost (allowed explicitly)."
        else
            echo "[entrypoint] FATAL: DATABASE_URL points at localhost:" >&2
            echo "[entrypoint]   ${DATABASE_URL%%://*}://...@${DATABASE_URL#*@}" >&2
            echo "[entrypoint] A container's localhost is itself, not the database host. Use" >&2
            echo "[entrypoint] the managed Postgres hostname (on Render: the *Internal*" >&2
            echo "[entrypoint] Database URL), or set ALLOW_LOCALHOST_DB=true if you really" >&2
            echo "[entrypoint] are running against the host's database." >&2
            exit 1
        fi
        ;;
esac

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
