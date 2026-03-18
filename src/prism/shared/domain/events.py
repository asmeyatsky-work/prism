"""
Shared Domain — Domain Events and Event Bus Port

Architectural Intent:
- Immutable domain events are the primary mechanism for cross-context communication
- Events are collected on aggregates and dispatched after persistence
- EventBusPort is defined here (domain layer) — implementations live in infrastructure
- All events carry tenant_id for multi-tenant routing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Base domain event — immutable, timestamped, tenant-scoped."""

    event_id: str = field(default_factory=lambda: str(uuid4()))
    aggregate_id: str = ""
    tenant_id: str = ""
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> str:
        return type(self).__name__


class EventBusPort(Protocol):
    """Port for publishing and subscribing to domain events."""

    async def publish(self, events: list[DomainEvent]) -> None: ...

    async def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None: ...


class EventHandler(Protocol):
    """Handler for a domain event."""

    async def handle(self, event: DomainEvent) -> None: ...
