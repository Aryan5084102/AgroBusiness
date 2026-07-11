# ADR 0002 — Decimal money and an append-only stock ledger

- **Status:** Accepted
- **Date:** 2026-07-11
- **Phase:** 0 (establishes rules enforced from Phase 2)

## Context

An ERP's correctness hinges on money and stock. Floating-point arithmetic causes
rounding drift that is unacceptable for invoices, tax, and payments. A mutable
`current_stock` column becomes wrong under concurrency, partial receipts, returns,
and transfers, and cannot be audited.

## Decision

1. **Money & quantity are `Decimal` end-to-end** and stored in PostgreSQL
   `NUMERIC` columns. No `float` in monetary or quantity calculations.
2. **Stock is an append-only `stock_movements` ledger.** Every change (purchase,
   sale, return, transfer, damage, expiry, adjustment, reservation, repair
   consumption, opening stock, reconciliation) is a movement row. `stock_balances`
   is a projection that can be rebuilt from the ledger; it is never the source of
   truth.
3. Stock is stored in the **smallest configured base unit**; display units are
   derived via configured conversions.
4. Finalized invoices and posted financial entries are **immutable**; corrections
   use returns, credit/debit notes, or reversal entries.

## Consequences

- Auditable, concurrency-safe inventory; FEFO/FIFO valuation is a query over the
  ledger.
- Slightly more write volume and the need for balance projections/summary tables
  for fast reads. Justified by correctness and traceability.
- Money helpers and `NUMERIC` schemas are mandatory building blocks in Phase 2+.
