# AgriFlow ERP

Production-grade wholesale **and** retail ERP for an agricultural-input business
(seeds, fertilizers, pesticides, machines, spare parts, tools). Modular monolith:
one FastAPI backend + one PostgreSQL database, one Next.js frontend.

> **Status: feature-complete and verified end to end on real Postgres.**
> 97 backend tests, ruff + mypy strict clean, 9 migrations zero-drift; frontend
> prettier/eslint/tsc/vitest clean and building; 28 Playwright specs walk **every
> screen as every one of the 3 roles** against a production build, plus the
> money paths (a counter sale, a stock correction, a collection), on Chromium
> and Firefox.
> The full buy→stock→sell→collect→service spine works end to end for retail and
> wholesale, with double-entry accounting, machine service, reporting, and
> hardening (rate limiting, concurrency-safe stock + numbering, backup/DR).
> Remaining nice-to-haves are listed under [Implementation phases](#implementation-phases).

Every role gets a working, permission-shaped interface: the sidebar only offers
screens that role can open, the dashboard is assembled from the panels they are
allowed to see, and any direct URL they are not entitled to shows a plain
"no access" screen instead of a failed request.

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

Screens: `/` (landing + login), `/status` (live system status), plus the
authenticated app — `/dashboard`, `/sales` (retail counter), `/wholesale`,
`/invoices`, `/customers`, `/collections`, `/products`, `/inventory`,
`/purchases`, `/service`, `/reports`, `/accounting`, `/audit`, `/settings`, plus
`/invoices/:id/bill` — the printable GST tax invoice.
Which of these a person sees is decided by their role.

### The retail counter

The counter works top to bottom: who is buying, then what they are buying, then
the money. **Customer name** and **mobile number** are required — they are what
the bill prints and what a khata is kept under — and the address is optional.
Typing a mobile already on file recognises that customer, fills in what the shop
knows, and attaches the sale to their existing account instead of opening a
second one; a new number is saved as a `walk_in` customer, coded `RC-<mobile>`.
Then pick a warehouse, add items, and take payment.

Ticking **Sale on credit (khata)** reveals an amount-taken-now box — leave it at
0 and the whole bill becomes a receivable against that same customer. A khata
sale answers to the same credit limit as a dealer order
(`SalesService._enforce_credit_limit`, mirroring the wholesale rule); a customer
with `credit_limit = 0` is treated as having no limit set, which is what a
counter-created customer starts with. Dealers with a real limit are still set up
one at a time via **New dealer** on the wholesale screen or the Customers screen.

### The bill

Taking payment downloads the bill as a PDF straight away — the counter never has
to ask for it. `frontend/src/features/invoices/invoicePdf.ts` draws the A4 tax
invoice client-side (seller and buyer blocks, HSN/quantity/rate lines, a
rate-wise CGST/SGST summary, the total in words, a signature block) on top of
`src/lib/pdf/pdfDocument.ts`, a small hand-rolled PDF writer, so no PDF library
or server round-trip is involved. It uses the base-14 Helvetica faces, which are
Latin-1 only: amounts read `Rs.` rather than `₹`, and a name in Devanagari cannot
be drawn.

The same invoice also has a web document at `/invoices/:id/bill`, which renders
any script and is reachable from the counter's receipt strip and from any row of
the invoice list. It renders outside `AppShell` so printing needs no
chrome-stripping — "Save as PDF" in the browser's print dialog gives a clean
one-page bill named after the invoice number. Both documents share their tax
maths (`features/invoices/gst.ts`) so they cannot disagree.

CGST/SGST are shown as equal halves of the stored GST, i.e. an intra-state
supply. There is no place-of-supply field yet, so an inter-state sale needing
IGST is not modelled.

### Roles

The shop runs on three roles, defined in `backend/app/core/permissions.py`:

| Role | Who | Can |
| ---- | --- | --- |
| **Owner** | the proprietor | everything — cost & margin, profit, books, repairs, users, settings, audit trail |
| **Counter / Sales** | counter staff | retail billing *and* wholesale/dealer orders, invoices, customers, collections; read-only catalogue and stock |
| **Store / Inventory** | godown keeper | products, stock adjustments and transfers, purchases and goods receipt |

Retail and wholesale are one role on purpose: the same person works both
counters, and the API guards both with `sales.create`. Nothing but Owner holds
`pricing.view_cost`, `report.view_profit`, `settings.manage` or `audit.view`, so
no staff account can see a margin or change how the shop is configured.

Roles are per-organization rows seeded from `DEFAULT_ROLES` at provisioning
time, so changing that table needs a migration for databases that already
exist — see `c9f1a70b34d2_phase9_collapse_roles_to_three.py`.

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

- **Backend** — `ruff` ✓, `ruff format --check` ✓, `mypy app` (strict) ✓,
  `pytest` ✓ (**97 tests**: unit + Hypothesis property tests + integration
  against a real PostgreSQL database, incl. a two-writer concurrency test),
  9 Alembic migrations apply from scratch (47 tables) with **zero drift**
  (`alembic check`), demo seed runs, and the auth flow was smoke-tested
  end-to-end over HTTP (login → session cookie → `/me`).
- **Frontend** — `prettier --check` ✓, `next lint` ✓, `tsc --noEmit` ✓,
  `vitest` ✓, `next build` ✓.
- **End to end** — `e2e/roles.spec.ts` signs in as each of the 3 demo roles and
  asserts that every screen the role covers renders real content, that screens
  outside the role are refused, and that the sidebar offers exactly the former
  and none of the latter. `e2e/flows.spec.ts` drives the money paths through the
  real UI: ringing up a counter sale, correcting stock, and taking a payment.
  Run against a production build:

  ```bash
  cd frontend && pnpm build
  npx next start -p 3100 &
  PLAYWRIGHT_BASE_URL=http://localhost:3100 npx playwright test --project=chromium
  ```

  `PLAYWRIGHT_SCREENSHOTS=1 npx playwright test e2e/screens.spec.ts` captures a
  screenshot of every screen, tab and dialog — desktop and mobile — into
  `frontend/screenshots/` for visual review.
- **API sweep** — every endpoint including the write paths was exercised against
  a live server (86 checks: create/update across the catalogue, customers,
  suppliers, staff, branches and warehouses; the full repair-job lifecycle;
  wholesale order → dispatch; goods receipt with landed cost; adjustments and
  transfers; CSV export; idempotent replay; refresh/logout), and every role was
  probed against every route to confirm it is refused exactly what it should be
  (217 checks, including cross-tenant id probes).

> **Cookie auth needs one origin.** The session cookie is `SameSite=Lax`, so the
> browser only sends it when the page and the API are same-site. In deployment
> Nginx serves the app on `/` and the API on `/api` from one origin
> ([`infra/nginx/nginx.conf`](infra/nginx/nginx.conf)). For local split-port dev,
> use the *same hostname* for both (`localhost:3000` → `localhost:8000`), not
> `127.0.0.1` for one and `localhost` for the other, and list the frontend origin
> in `CORS_ORIGINS`.

Critical-module coverage: money kernel 98%, pricing engine 99%, FEFO/inventory
covered by property + integration tests.

Not yet exercised on this machine: `docker compose up` (no Docker installed) and
the WebKit Playwright project (its `libavif13` system package needs root). CI
(`.github/workflows/ci.yml`) runs the full stack against service containers on
all three engines.

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
| 4     | Retail POS: customers, sale → pricing engine → FEFO stock deduction → immutable invoice (pricing snapshot) → split payments, idempotency keys, walk-in-must-pay rule | **Done** (offline queue pending) |
| —     | Full role-shaped UI: every screen built, permission-gated navigation, role-aware dashboard, no-access screen, mobile drawer, toasts, design system | **Done** |
| 5     | Wholesale: sales orders/quotations, dealer/wholesale pricing, credit-limit check + approval override, FEFO stock reservation, dispatch → release → deduct → wholesale credit invoice | **Done** (partial dispatch/e-way-bill pending) |
| 6     | Accounting & collections: double-entry ledger (balanced journals), chart of accounts, FIFO payment allocation across invoices, customer ledger | **Done** |
| 7     | Machines & service: warranties + claims, repair jobs, spare-part consumption/return posted to the stock ledger, warranty-covered billing | **Done** |
| 8     | Reports & compliance: owner dashboard, GST summary, sales/purchase registers, stock valuation, CSV export, documents metadata, in-app notifications | **Done** (PDF export pending) |
| 9     | Hardening: login rate limiting, concurrency-safe stock + document numbering (advisory lock), backup/restore scripts, security & release checklists | **Done** (RLS, 2FA, perf load tests pending) |

### Deferred sub-items (not built)
Offline POS queue · partial dispatch / e-way-bill · dedicated thermal-printer
invoice layout (browser print works today) · PDF report export (CSV works) ·
PostgreSQL RLS · 2FA · malware-scan on upload.

## Documentation

- Architecture decisions: [`docs/adr/`](docs/adr/)
- Security checklist: [`docs/SECURITY.md`](docs/SECURITY.md)
- Production release checklist: [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md)
- Backup/restore: [`scripts/backup_db.sh`](scripts/backup_db.sh),
  [`scripts/restore_db.sh`](scripts/restore_db.sh)

## License

Proprietary — all rights reserved (client engagement).
