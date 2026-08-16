# Deployment — backend (Render)

The backend image is self-sufficient: `docker-entrypoint.sh` runs
`alembic upgrade head` on every boot (idempotent) and the server binds to
`$PORT` if the platform assigns one. What the platform still has to supply is
configuration — without it the app falls back to development defaults and
points at `localhost`, which surfaces as `500` on every database-backed
endpoint while `/api/v1/live` still returns `200`.

## Required environment variables

| Variable | Value | Why |
| --- | --- | --- |
| `DATABASE_URL` | Render Postgres **Internal Database URL** | Without it the app dials `localhost:5432`. A pasted `postgres://…` is normalised to `postgresql+asyncpg://` automatically. |
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` | Signs auth tokens. The default is public and forgeable. |
| `ENVIRONMENT` | `staging` or `production` | Gates the strong-secret check and JSON logging. |
| `CORS_ORIGINS` | the frontend's exact origin | Credentials are sent on every request, so browsers reject `*`. |
| `COOKIE_SAMESITE` | `none` for a cross-domain frontend, else `lax` | See below. |

Optional: `REDIS_URL` (only the `/api/v1/ready` probe uses it — login rate
limiting is in-process, so a missing Redis reports `degraded` but breaks
nothing), and the `S3_*` variables for attachment storage.

Use the **Internal** database URL when the database and service share a region:
it needs no TLS parameters and does not leave Render's network. The external
URL requires appending `?ssl=require`.

## Cookies and the frontend's domain

Auth travels in HTTP-only cookies, so the frontend's domain decides the
setting:

- **Frontend proxied under the API's hostname** — keep `COOKIE_SAMESITE=lax`.
- **Frontend on its own domain** (Vercel, Netlify, a second Render service) —
  every request is cross-site, and browsers only attach cookies to those when
  `SameSite=None`, which they in turn only accept when `Secure` is set. Use
  `COOKIE_SAMESITE=none`; `Secure` is then applied automatically, and startup
  refuses to proceed if you force `COOKIE_SECURE=false`.

The failure mode when this is wrong is quiet: `/auth/login` returns `200` with
a user payload, the browser discards the cookie, and the next request 401s.

## Seeding demo data

`SEED_ON_START=true` runs `python -m app.seed` after migrations, creating the
demo organization and the one-click sign-in accounts. It requires
`ENVIRONMENT=staging` — `app/seed.py` refuses to run under `production`.
**Unset it after the first successful deploy**, otherwise every restart
re-runs the seed.

## Frontend (Vercel)

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `https://<backend>.onrender.com` — no trailing slash, the client concatenates paths directly |
| `NEXT_PUBLIC_SHOW_DEMO_ACCOUNTS` | `true` to show the login page's one-click demo panel |

`NEXT_PUBLIC_*` values are inlined at build time, so changing either one needs a
redeploy, not just a restart — and they must be set for every environment
(Production/Preview/Development) that should use them.

The demo panel defaults to the build type: visible under `next dev`, hidden in
any production build — which is every hosted deploy. That is why a deployed demo
has to set the flag explicitly. When it is off, the account list is stripped
from the JavaScript bundle entirely rather than merely hidden, so only turn it
on where the database was seeded with demo data.

## First deploy checklist

1. Create the Postgres instance and copy its Internal Database URL.
2. Set the variables above on the service.
3. Deploy. The logs should show `[entrypoint] running database migrations…`
   followed by the Alembic revisions applying.
4. `curl https://<service>/api/v1/ready` — `database` should read `up`.
   (First request after idle takes ~30s on Render's free tier; the instance
   spins down when unused.)
5. Sign in from the frontend and confirm the session survives a page reload —
   that is what proves the cookie attributes are right.
