# AgriFlow ERP

Production-grade wholesale **and** retail ERP for an agricultural-input business
(seeds, fertilizers, pesticides, machines, spare parts, tools). Modular monolith:
one FastAPI backend + one PostgreSQL database, one Next.js frontend.

> **Status: Phases 0–3 + pricing engine — complete and verified on real Postgres.**
> Auth/RBAC, the append-only inventory ledger with FEFO, the pricing/tax engine,
> and purchases (PO → goods receipt → landed cost → stock) are implemented and
> tested. Later phases add remaining business modules. See
> [Implementation phases](#implementation-phases).

Branding (name, logo, colours, address, invoice details) is configurable and not
hardcoded in source.

---

## Repository layout

```
.
├── backend/        FastAPI modular monolith (Python 3.12, async SQLAlchemy)
├── frontend/       Next.js App Router (TypeScript strict, SCSS modules)
├── infra/nginx/    Reverse-proxy config
├── docs/adr/       Architecture Decision Records
├── docker-compose.yml
└── .github/workflows/ci.yml
```

Frontend code lives entirely under `frontend/`; backend under `backend/`.

## Tech stack

| Layer     | Choices                                                                       |
| --------- | ----------------------------------------------------------------------------- |
| Frontend  | Next.js 15, React 19, TypeScript (strict), SCSS Modules + CSS tokens, TanStack Query/Table, Redux Toolkit, React Hook Form, Zod, Vitest + RTL, Playwright |
| Backend   | FastAPI, Pydantic v2, SQLAlchemy 2 (async), PostgreSQL, Alembic, Redis, Celery, structlog; Ruff + mypy (strict); Pytest + Hypothesis |
| Infra     | Docker Compose (Postgres, Redis, MinIO), Nginx, GitHub Actions, pnpm workspace |

## Prerequisites

- Node 20+ and pnpm 10+
- Python 3.10+ (CI and Docker use 3.12)
- Docker + Docker Compose (for the full stack; optional for app-only dev)

## Quick start — full stack (Docker)

```bash
cp .env.example .env          # adjust secrets before anything non-local
docker compose up --build
# Frontend + API via Nginx:  http://localhost:8080
# API docs (dev):            http://localhost:8000/docs
# MinIO console:             http://localhost:9001
```

## Quick start — backend only

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload        # http://localhost:8000

# Quality gates
ruff check . && ruff format --check .
mypy app
pytest
```

Health endpoints: `/api/v1/live`, `/api/v1/ready`, `/api/v1/health`. Without a
running Postgres/Redis, `/health` reports **degraded** (each dependency `down`)
rather than erroring — by design.

## Quick start — frontend only

```bash
cd frontend
pnpm install
cp .env.example .env.local
pnpm dev                              # http://localhost:3000

# Quality gates
pnpm format:check && pnpm lint && pnpm typecheck && pnpm test && pnpm build
# E2E (installs browsers first): npx playwright install && pnpm e2e
```

Pages: `/` (landing + login), `/status` (live system status), `/dashboard`
(authenticated shell demo).

## Environment variables

| Scope    | File                   | Notes                                    |
| -------- | ---------------------- | ---------------------------------------- |
| Root     | `.env.example`         | docker compose (Postgres/MinIO/secrets)  |
| Backend  | `backend/.env.example` | validated by `app/core/config.py`        |
| Frontend | `frontend/.env.example`| only `NEXT_PUBLIC_*` reaches the browser |

Secrets are never committed. `SECRET_KEY` must be a strong value outside local
dev — the backend refuses to start in `production` with the insecure default.

## Verification status

Run locally and passing:

- **Backend** — `ruff` ✓, `ruff format --check` ✓, `mypy app` (strict, 68 files) ✓,
  `pytest` ✓ (**64 tests**: unit + Hypothesis property tests + integration
  against a real PostgreSQL database), 3 Alembic migrations apply from scratch
  with **zero drift** (`alembic check`), demo seed runs, and the auth flow was
  smoke-tested end-to-end over HTTP (login → session cookie → `/me`).
- **Frontend** — `prettier --check` ✓, `next lint` ✓, `tsc --noEmit` ✓,
  `vitest` ✓ (3/3), `next build` ✓.

Critical-module coverage: money kernel 98%, pricing engine 99%, FEFO/inventory
covered by property + integration tests.

Not yet exercised on this machine (no Docker installed): `docker compose up` and
Playwright browser runs. CI (`.github/workflows/ci.yml`) runs both against
service containers.

### Running backend integration tests locally

Integration tests need a PostgreSQL database. With Docker: `docker compose up -d
postgres`. Without Docker, a user-owned instance works too — point
`TEST_DATABASE_URL` at any reachable Postgres, e.g.:

```bash
export TEST_DATABASE_URL="postgresql+asyncpg://agriflow@127.0.0.1:5432/agriflow_test"
cd backend && pytest
```

If no database is reachable, integration tests **skip** (with a clear reason)
rather than fail; unit/property tests always run.

## Implementation phases

| Phase | Scope                                             | State    |
| ----- | ------------------------------------------------- | -------- |
| 0     | Foundation: monorepo, Docker, config, logging, errors, health, design tokens, app shell, CI | **Done** |
| 1     | Auth (Argon2, rotating refresh + reuse detection, cookies), orgs, branches, warehouses, users, action-level RBAC, audit log, tenant isolation | **Done** |
| 2     | Catalogue (products + JSONB attrs, units), append-only stock ledger, balances, batches/serials, FEFO issue, transfer, negative-stock + expiry guards | **Done** |
| —     | Centralised pricing engine + GST tax (priority resolution, decimal-safe totals, margin/discount warnings) | **Done** |
| 3     | Suppliers, purchase orders, goods receipt (posts to stock ledger), landed cost, branch document numbering, duplicate-invoice detection | **Done** |
| 4     | Retail POS + offline                              | Planned  |
| 5     | Wholesale                                         | Planned  |
| 6     | Accounting & collections                          | Planned  |
| 7     | Machines & service                                | Planned  |
| 8     | Reports & compliance                              | Planned  |
| 9     | Hardening (security, perf, DR, a11y)              | Planned  |

## Documentation

- Architecture decisions: [`docs/adr/`](docs/adr/)
- More guides (API, permission matrix, deployment, backup/restore, offline sync,
  security checklist, user manual) are added alongside the phases that introduce
  those subsystems.

## License

Proprietary — all rights reserved (client engagement).
