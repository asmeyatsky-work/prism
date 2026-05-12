# 0001 — Canonical stack: Python 3.12 + FastAPI + GCP

Status: Accepted
Date: 2026-05-12

## Context

`Architectural Rules — 2026.md §1` lists per-domain stack defaults:

- Rust for ledgers, parsers, hot-path APIs (p99 < 50ms), cryptography
- Python 3.12+ for AI/ML, agentic orchestration, data, CLI, prototypes
- TypeScript + React for frontends
- GCP for cloud (Cloud Run, Secret Manager, IAM, Workload Identity)

## Decision

PRISM v0.1 is **entirely Python 3.12 + FastAPI + GCP** because every bounded
context — Catalogue, Commerce, Intelligence, Discovery, Try-On, Payment,
Agentic CX, Gateway — is *AI/ML and orchestration heavy*. None of the
v0.1 surfaces meet the p99 < 50ms threshold that would mandate Rust.

The frontend is intentionally deferred to a TypeScript + React app in a
later milestone; the demo currently uses a static HTML page served by the
Cloud Run service.

## Consequences

- We accept Python's GIL overhead for the hot path; this is acceptable at
  current latency SLOs.
- A Rust ledger crate is anticipated for the Payment context once
  transaction volume justifies it. That move will require a new ADR.
