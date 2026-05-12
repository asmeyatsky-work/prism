# Architecture Decision Records (ADRs)

Each ADR captures a *non-trivial* architectural choice and the reasoning
behind it. Per `Architectural Rules — 2026.md` §0, deviations from the
canonical stack and resolutions of PRD ↔ rule conflicts must be recorded
here as ADRs.

Conventions:

- Filename: `NNNN-kebab-title.md` — monotonically increasing.
- Status: `Accepted`, `Superseded by NNNN`, or `Deprecated`.
- One decision per file. Keep them short — ADRs are not design docs.

Index:

| ID   | Title                                          | Status   |
|------|------------------------------------------------|----------|
| 0001 | Canonical stack: Python 3.12 + FastAPI + GCP   | Accepted |
| 0002 | Pinned lockfile via pip-tools                  | Accepted |
| 0003 | Tenant-id rollout across MCP tool surfaces     | Accepted |
| 0004 | Audit sink: structured logs → Cloud Logging    | Accepted |
| 0005 | Observability: contextvar correlation IDs      | Accepted |
