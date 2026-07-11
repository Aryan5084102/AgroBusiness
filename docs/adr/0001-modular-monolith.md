# ADR 0001 — Modular monolith over microservices

- **Status:** Accepted
- **Date:** 2026-07-11
- **Phase:** 0

## Context

AgriFlow ERP spans many domains (catalogue, inventory, purchases, POS, wholesale,
accounting, service). The team is small and the first release must ship quickly
and be operable by one person. Microservices would add network boundaries,
distributed transactions, and deployment complexity before the domain model has
stabilised.

## Decision

Build a **modular monolith**: a single FastAPI application and a single Postgres
database. Each business domain is an isolated module under `app/modules/<domain>`
with its own router, service, repository, schemas, models, and tests. Modules
communicate only through published service interfaces and domain events — never
by reaching into another module's repository or tables.

## Consequences

- Simple local dev, one deploy artifact, straightforward transactions.
- Strong internal boundaries keep future extraction to services cheap: a module
  can become an independent service because its seams already exist.
- Requires discipline: cross-module imports of repositories/models are
  disallowed and enforced in review. Shared concerns live in `app/common`.
