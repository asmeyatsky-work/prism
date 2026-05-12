"""
Shared Infrastructure — Audit Sink Adapters

Architectural Intent:
- Implements AuditSinkPort from the domain layer.
- InMemoryAuditSink: deterministic, append-only sink for tests and demo.
- StructlogAuditSink: emits JSON log lines on a dedicated logger so a
  Cloud Logging sink / BigQuery export can route them to an immutable bucket
  with separate IAM (Rules §4 — "Append-only, separate IAM").

Layer: infrastructure
Implements: prism.shared.domain.audit.AuditSinkPort
Stack: canonical (structlog).
"""

from __future__ import annotations

import logging
from typing import Any

from prism.shared.domain.audit import AuditEvent


class InMemoryAuditSink:
    """Append-only in-memory audit sink. Reads are read-only views."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def record(self, event: AuditEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)


class StructlogAuditSink:
    """
    Audit sink that writes to a dedicated 'prism.audit' logger.

    Production wiring: route this logger to Cloud Logging with a sink that
    exports to an immutable BigQuery dataset (separate IAM, append-only).
    """

    def __init__(self, logger_name: str = "prism.audit") -> None:
        self._log: Any = logging.getLogger(logger_name)

    async def record(self, event: AuditEvent) -> None:
        self._log.info("audit_event", extra={"audit": event.to_dict()})
