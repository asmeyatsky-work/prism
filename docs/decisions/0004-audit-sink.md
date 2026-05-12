# 0004 — Audit sink: structured logs → Cloud Logging → BigQuery

Status: Accepted
Date: 2026-05-12

## Context

Rules §4 mandates: "Every write emits an audit event: actor, action,
before/after hash. Append-only, separate IAM."

## Decision

- `AuditSinkPort` lives in `prism.shared.domain.audit`.
- Two adapters in `prism.shared.infrastructure.audit_sinks`:
  - `InMemoryAuditSink` for tests + demo (append-only list, read-only
    snapshot view).
  - `StructlogAuditSink` for production — writes to a dedicated
    `prism.audit` Python logger.
- Production Cloud Logging routes the `prism.audit` log channel to a
  BigQuery dataset with **deny-delete** IAM policy. Only the audit
  service account can write to the underlying log bucket. PRISM service
  accounts only have `logging.logEntries.create` on the channel — they
  cannot read, mutate, or delete the dataset.
- Audit events carry **hashes** of the before/after aggregate state, not
  the raw payloads. This keeps the audit trail PII-free by construction
  (Rules §6 — "Zero PII").

## Consequences

- Audit failures must not block writes. The sink is best-effort with a
  bounded retry; misses are alerted on a dedicated Cloud Monitoring
  policy (TBD).
- Forensic replays use hashes to detect divergence between primary store
  and event log — full payload reconstruction requires the primary store.
