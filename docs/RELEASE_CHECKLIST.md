# Production release checklist — AgriFlow ERP

## Pre-deploy
- [ ] `SECRET_KEY` set to a strong, unique value (48+ bytes). App refuses the
      insecure default in `production`.
- [ ] `ENVIRONMENT=production`, `DEBUG=false`.
- [ ] `CORS_ORIGINS` restricted to the real frontend origin(s).
- [ ] Database URL points at the managed Postgres; credentials in a secret store.
- [ ] Redis + object storage (S3/MinIO) reachable; buckets created.
- [ ] TLS termination + HSTS configured at Nginx/edge.

## Quality gates (CI must be green)
- [ ] Backend: `ruff check` · `ruff format --check` · `mypy app` · `pytest`.
- [ ] Migrations apply cleanly from scratch: `alembic upgrade head`; `alembic check`
      reports no drift.
- [ ] Frontend: `prettier --check` · `next lint` · `tsc --noEmit` · `vitest` · `next build`.
- [ ] Playwright smoke suite passes on Chromium/Firefox/WebKit.

## Data & migrations
- [ ] Run `alembic upgrade head` against production during the deploy window.
- [ ] Do **not** run `app/seed.py` in production (it refuses, but confirm).

## Backup & DR
- [ ] `scripts/backup_db.sh` scheduled (cron/systemd timer) with encryption.
- [ ] **Restore test** performed with `scripts/restore_db.sh` into a scratch DB.
- [ ] Retention + off-site copy configured.

## Observability
- [ ] Structured logs shipped to aggregation; correlation ids preserved.
- [ ] Health probes wired: `/api/v1/live` (liveness), `/api/v1/ready` (readiness).
- [ ] Alerting on failed background jobs and failed logins spikes.

## Post-deploy verification
- [ ] Owner login over HTTPS → session cookie set → `/api/v1/auth/me` works.
- [ ] Create a product, receive stock, ring a retail sale, receive a payment.
- [ ] Dashboard + GST summary render with real data.
- [ ] Audit log records the login.

## Sign-off
- [ ] Owner reviewed GST/tax outputs.
- [ ] Owner approved go-live.
