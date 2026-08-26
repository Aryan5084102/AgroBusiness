# Deployment — backend (Render)

The backend image is self-sufficient: `docker-entrypoint.sh` runs
`alembic upgrade head` on every boot (idempotent) and the server binds to
`$PORT` if the platform assigns one. What the platform still has to supply is
configuration.

The app detects that it is running on a managed platform (Render, Heroku, Fly,
Railway, Cloud Run all export a marker variable) and **refuses to start** if it
is still on development defaults, listing every missing variable at once. This
replaces the old failure mode, where an unconfigured service booted happily,
answered `/api/v1/live` with `200`, and returned `500` on every database-backed
endpoint — or, for CORS, failed only in the browser, with nothing in the server
log at all.

`render.yaml` at the repo root declares the database and the service together,
wiring `DATABASE_URL` automatically via `fromDatabase`. Apply it with **New +
→ Blueprint**. Note that a blueprint does not adopt a service that was created
by hand — an existing service needs the variables below set on its Environment
tab instead.

## Required environment variables

Two variables have no safe default, because only you know their values. A
hosted service refuses to start without them:

| Variable | Value | Why |
| --- | --- | --- |
| `DATABASE_URL` | the managed Postgres connection string | Without it the app dials `localhost:5432`. A pasted `postgres://…` is normalised to `postgresql+asyncpg://` automatically. |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | Signs auth tokens. The default is public and forgeable. |

Derived automatically — set them only to override:

| Variable | Derived as | |
| --- | --- | --- |
| `ENVIRONMENT` | `staging` when a hosting platform is detected, else `development` | Gates the strong-secret check and JSON logging. |
| `COOKIE_SAMESITE` | `none` when `CORS_ORIGINS` names a non-local origin, else `lax` | Needing CORS at all means the frontend is a cross-site caller. See below. |
| `COOKIE_SECURE` | `true` on any hosted platform, or whenever SameSite resolves to `none` | Hosted platforms are HTTPS-only; browsers also discard `SameSite=None` cookies that are not `Secure`. |

`CORS_ORIGINS` is **not** required. The frontend proxies `/api/*` through its own
origin, so the browser never makes a cross-origin request and there is no
preflight to allow. Set it only for a client that does call this API
cross-origin; an unset value logs a startup warning and blocks nothing.

Optional: `REDIS_URL` (only the `/api/v1/ready` probe uses it — login rate
limiting is in-process, so a missing Redis reports `degraded` but breaks
nothing), and the `S3_*` variables for attachment storage.

The entrypoint refuses to boot when `DATABASE_URL` is missing or points at
localhost, printing what to fix instead of an asyncpg traceback. `ALLOW_LOCALHOST_DB=true`
overrides the localhost check for `docker run --network host` against a database
on the host machine.

Use the **Internal** database URL when the database and service share a region:
it needs no TLS parameters and does not leave Render's network.

## Using a Postgres somewhere other than Render

Render's free plan allows one Postgres instance and deletes it after 30 days, so
the database often has to live elsewhere. Any Postgres 14+ works — Neon,
Supabase, Aiven — and only `DATABASE_URL` changes; nothing in the image or the
service config cares where the database is.

Paste the provider's connection string **verbatim**. `_normalise_asyncpg_query`
in `app/core/config.py` rewrites the parts asyncpg would otherwise reject:

| Provider writes | Stored as | Why |
| --- | --- | --- |
| `postgres://` / `postgresql://` | `postgresql+asyncpg://` | selects the async driver |
| `?sslmode=require` | `?ssl=require` | asyncpg's keyword is `ssl`; it has no `sslmode` |
| `&channel_binding=require` | *(dropped)* | a libpq 14 parameter asyncpg never accepted |

That translation matters because SQLAlchemy's asyncpg dialect forwards the query
string to `asyncpg.connect()` untouched, and that signature accepts no
`**kwargs`. An unrewritten `sslmode` is therefore a `TypeError` on the *first
query* — startup succeeds, `/api/v1/live` returns `200`, and only real traffic
fails.

**Connection pooling.** Neon and Supabase both publish two endpoints. Prefer the
**direct** one (Neon: the host *without* `-pooler`; Supabase: port `5432`, not
`6543`). The pooled endpoints run PgBouncer in transaction mode, which is
incompatible with the prepared statements asyncpg caches by default — the
symptom is intermittent `prepared statement "__asyncpg_stmt_x__" does not exist`
under load. This app opens one SQLAlchemy pool per instance and does not need an
external pooler. If you must use one, append
`&prepared_statement_cache_size=0` (passed through untouched by the rewrite
above).

**Region.** Put the database in the same region as the Render service. This is a
cross-network hop now rather than an internal one, and every query pays the
latency twice — once in the API, once in the migration step at boot.

## Cookies and the frontend's domain

Auth travels in HTTP-only cookies, so the frontend's domain decides the
setting:

- **Frontend proxied under the API's hostname** — it is same-origin, never
  appears in `CORS_ORIGINS`, and SameSite resolves to `lax`.
- **Frontend on its own domain** (Vercel, Netlify, a second Render service) —
  every request is cross-site, and browsers only attach cookies to those when
  `SameSite=None`, which they in turn only accept when `Secure` is set. Setting
  `CORS_ORIGINS` to that domain resolves SameSite to `none` and `Secure` to
  `true` on its own; startup refuses to proceed if you force
  `COOKIE_SECURE=false` against it.

The failure mode when this is wrong is quiet: `/auth/login` returns `200` with
a user payload, the browser discards the cookie, and the next request 401s.

## Seeding demo data

`SEED_ON_START=true` runs `python -m app.seed` after migrations, creating the
demo organization and the one-click sign-in accounts. It requires
`ENVIRONMENT=staging` — `app/seed.py` refuses to run under `production`.

On a database that already holds an organization the seed leaves every business
row alone and only reconciles the demo *logins*: the accounts the login page
offers are created if missing, renamed from their pre-`c9f1a70b34d2` emails if
the old ones are still there, unlocked, and re-pointed at the one role each is
advertised with. That is idempotent, so leaving `SEED_ON_START=true` on a demo
deployment is safe and is what keeps its sign-in buttons working across a role
rename. Unset it on any instance holding data you care about.

## Frontend (Vercel)

| Variable | Value |
| --- | --- |
| `API_PROXY_TARGET` | `https://<backend>.onrender.com` — no trailing slash |
| `NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS` | `true` to show the login page's one-click demo panel |

The browser calls `/api/*` on the frontend's own origin and `next.config.mjs`
rewrites those to `API_PROXY_TARGET` server-side. Nothing the browser sends is
cross-origin, which removes two failure modes that previously depended on the
backend being configured exactly right:

- **CORS.** There is no preflight to reject, so a wrong `CORS_ORIGINS` cannot
  block the app. The browser used to report `Disallowed CORS origin` while the
  server logged an ordinary request.
- **Cookie SameSite.** Same-origin requests carry cookies without
  `SameSite=None`, so the quiet variant — `200` from `/auth/login`, cookie
  discarded, `401` on the next call — cannot happen.

`NEXT_PUBLIC_API_BASE_URL` is still read as a fallback upstream so existing
deployments keep working, but it no longer reaches the browser and new setups
should use `API_PROXY_TARGET`.

Both values are applied at build time, so changing either needs a redeploy, not
just a restart — and they must be set for every environment
(Production/Preview/Development) that should use them.

One limit worth knowing: proxied requests pass through Vercel's function layer,
which caps request bodies (4.5 MB on serverless). Nothing in the app posts
multipart bodies today, so this only matters if attachment upload is added
later — that would want a direct-to-S3 presigned upload regardless.

The demo panel defaults to the build type: visible under `next dev`, hidden in
any production build — which is every hosted deploy. That is why a deployed demo
has to set the flag explicitly. When it is off, the account list is stripped
from the JavaScript bundle entirely rather than merely hidden, so only turn it
on where the database was seeded with demo data.

## First deploy checklist

1. Create the Postgres instance and copy its connection string.
2. Set the three required variables above on the service.
3. Deploy. The logs should show `[entrypoint] running database migrations…`
   followed by the Alembic revisions applying. If a variable is missing, the
   process exits during startup with a numbered list of what to fix.
4. `curl https://<service>/api/v1/ready` — `environment` should read `staging`
   and `database` should read `up`. `redis` reads `down` unless you set
   `REDIS_URL`; that is expected and harmless.
   (First request after idle takes ~30s on Render's free tier; the instance
   spins down when unused.)
5. Sign in from the frontend and confirm the session survives a page reload —
   that is what proves the cookie attributes are right.
