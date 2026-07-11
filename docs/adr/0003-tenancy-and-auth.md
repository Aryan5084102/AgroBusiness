# ADR 0003 — Tenancy derivation and authentication model

- **Status:** Accepted
- **Date:** 2026-07-11
- **Phase:** 0 (implemented in Phase 1)

## Context

The system is multi-organization and multi-branch. Trusting an `organization_id`
or `branch_id` from the client would allow cross-tenant data access. Auth tokens
in `localStorage` are exposed to XSS.

## Decision

1. **Tenant context is derived from the authenticated session** (JWT claims),
   never from client-supplied body/query values. Every business table carries
   `organization_id` / `branch_id` (+ `warehouse_id` where relevant), and
   isolation is enforced in the service layer and with PostgreSQL Row-Level
   Security where appropriate.
2. **Auth**: Argon2 password hashing; short-lived access token + rotating refresh
   token with reuse detection; tokens delivered via **HTTP-only, Secure cookies**
   (not `localStorage`); CSRF protection on cookie-based mutations; account
   lockout; optional 2FA.
3. **RBAC is action-level** (`sales.finalize`, `pricing.view_cost`, …) and
   enforced on **every** API route. Hiding UI controls is cosmetic only.
4. **Every request has a correlation id** (`X-Request-ID`), bound to structured
   logs; sensitive keys are redacted before logging.

## Consequences

- No endpoint accepts tenant identifiers from the client for authorization.
- Consistent error envelope `{error:{code,message,field_errors,correlation_id}}`;
  internal details and stack traces are never returned to clients.
- Foundation pieces (config, logging redaction, correlation middleware, error
  handlers, security headers) are in place in Phase 0; token issuance and RLS
  land in Phase 1.
