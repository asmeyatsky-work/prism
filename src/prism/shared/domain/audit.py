"""
Shared Domain — Audit Event Port

Architectural Intent (Rules §4):
- Every write must emit an audit event: actor, action, before/after hash.
- Append-only sink with separate IAM (e.g. GCP Logging audit bucket / BigQuery
  partitioned table with deny-delete policy).
- Port lives in domain. Adapters (in-memory for tests, GCP Logging in prod)
  implement it.

Layer: domain
Ports: AuditSinkPort (this file)
MCP: not exposed (audit is internal observability, not a tool surface).
Stack: canonical (Python 3.12 + Protocol).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


def _hash(payload: Any) -> str:
    """Stable SHA-256 of any JSON-serialisable payload (None -> empty hash)."""
    if payload is None:
        return ""
    canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


@dataclass(frozen=True)
class AuditEvent:
    """
    Immutable record of a single mutating action.

    `before_hash` / `after_hash` are SHA-256 digests of the canonical JSON
    serialisation of the aggregate state — full payloads are intentionally
    not stored to keep the audit trail PII-free.
    """

    actor: str
    action: str
    aggregate_type: str
    aggregate_id: str
    tenant_id: str
    before_hash: str = ""
    after_hash: str = ""
    correlation_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event_id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def for_change(
        cls,
        *,
        actor: str,
        action: str,
        aggregate_type: str,
        aggregate_id: str,
        tenant_id: str,
        before: Any = None,
        after: Any = None,
        correlation_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        return cls(
            actor=actor,
            action=action,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            tenant_id=tenant_id,
            before_hash=_hash(before),
            after_hash=_hash(after),
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["occurred_at"] = self.occurred_at.isoformat()
        return d


class AuditSinkPort(Protocol):
    """Append-only audit sink. Implementations MUST be write-only."""

    async def record(self, event: AuditEvent) -> None: ...
