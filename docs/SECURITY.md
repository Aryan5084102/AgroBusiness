# Security checklist — AgriFlow ERP

Status of controls implemented in the backend. Items marked ☐ are designed-for
but not yet implemented; they are tracked for the hardening phase.

## Authentication & sessions
- ☑ Argon2id password hashing (`app/core/security.py`).
- ☑ Short-lived access token (JWT, HS256) + rotating refresh token.
- ☑ Refresh-token **reuse detection** revokes the whole session.
- ☑ Tokens delivered as **HTTP-only, SameSite=Lax cookies** (Secure in prod);
  never in `localStorage`.
- ☑ Account lockout after repeated failed logins.
- ☑ Per-IP **rate limiting** on login (`app/core/ratelimit.py`).
- ☐ Optional TOTP 2FA.
- ☐ CSRF double-submit token for cookie-based mutations (SameSite mitigates most).

## Authorization & tenancy
- ☑ Action-level RBAC enforced on every protected route (`require_permission`).
- ☑ Tenant identifiers derived from the verified token, **never** the client body.
- ☑ Service-layer tenant scoping on all queries.
- ☐ PostgreSQL Row-Level Security as defence-in-depth (planned).

## Data integrity
- ☑ Decimal money end-to-end; PostgreSQL `NUMERIC` columns; no floats.
- ☑ Append-only stock ledger; balances are rebuildable projections.
- ☑ Balanced double-entry journal (debit == credit enforced).
- ☑ Immutable finalized invoices (no update path; corrections via returns/notes).
- ☑ Optimistic locking (`version_id`) on concurrently edited records.
- ☑ Row-lock serialization prevents overselling under concurrency (tested).
- ☑ Advisory-lock serialization prevents duplicate document numbers (tested).
- ☑ Idempotency keys on critical mutations (POS sale).

## Transport & headers
- ☑ Security headers (`X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`) on every response + at Nginx.
- ☑ Restricted CORS (explicit origins, credentials).
- ☐ HSTS + TLS termination (configure at the edge/Nginx in production).

## Secrets & logging
- ☑ Secrets only via environment variables; none committed.
- ☑ Production refuses to boot with the insecure default `SECRET_KEY`.
- ☑ Structured logs redact password/token/secret keys.
- ☑ No stack traces returned to clients; correlation id on every error.

## Auditing
- ☑ Append-only audit log for auth events (login/lockout/reuse).
- ☐ Extend audit coverage to price/cost changes, discount/credit overrides,
  stock adjustments, document downloads, settings changes.

## Files & storage
- ☑ Object-storage keys stored server-side, never exposed; signed-URL abstraction.
- ☐ File-type/size validation + malware-scan adapter on upload.

> Tax/GST outputs must be reviewed by a qualified accountant before production
> use. The presence of a report does not constitute legal compliance.
