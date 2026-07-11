# ADR 0004 — Frontend state, styling, and offline strategy

- **Status:** Accepted
- **Date:** 2026-07-11
- **Phase:** 0

## Context

Mixing server cache and client state in one store leads to stale data and complex
invalidation. Styling needs to be themeable/white-label without source edits.
The POS must keep billing during brief internet loss.

## Decision

1. **Server state → TanStack Query.** **Client state → Redux Toolkit**, and only
   for: authenticated user, POS session, offline queue, and global UI settings.
   API data already in TanStack Query is never duplicated into Redux.
2. **Styling → SCSS Modules + CSS custom properties.** Design tokens (colours,
   spacing, radius, shadows, z-index) are defined once in `src/styles/tokens` and
   emitted as `:root` custom properties, so branding/themes are runtime overrides.
   No inline CSS; components stay under ~400 lines by splitting into
   components/hooks/schemas/services.
3. **Backend is the pricing/tax authority.** The frontend may show estimates but
   the backend recalculates before finalization; each invoice line stores a
   pricing snapshot.
4. **Offline POS** caches products/prices/stock in IndexedDB (Dexie). Offline
   invoices carry a client-generated UUID; sync is idempotent; conflicts surface
   on a resolution screen and are never silently overwritten.

## Consequences

- Clear ownership of state; predictable caching.
- Themeable UI with no code changes; accessible tokens meeting WCAG AA.
- Dexie/offline and the pricing engine are implemented in Phases 4–5; the token
  system, provider tree, and API error contract are established in Phase 0.
