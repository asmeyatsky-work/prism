"""
Shared Domain — Base Entity and Aggregate Root

Architectural Intent:
- Provides immutable base classes for all domain entities across bounded contexts
- AggregateRoot collects domain events for dispatch after persistence
- All identity is string-based (UUID) for portability across infrastructure
- Frozen dataclasses enforce immutability per skill2026 Rule 3
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import uuid4

from prism.shared.domain.events import DomainEvent


def _new_id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class Entity:
    """Base entity with identity and timestamp tracking."""

    id: str = field(default_factory=_new_id)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def _touch(self) -> dict:
        return {"updated_at": datetime.now(UTC)}


@dataclass(frozen=True)
class AggregateRoot(Entity):
    """
    Base aggregate root that collects domain events.

    Events are accumulated via immutable replacement and dispatched
    after successful persistence by the application layer.
    """

    domain_events: tuple[DomainEvent, ...] = field(default=())

    def _add_event(self, event: DomainEvent) -> AggregateRoot:
        return replace(
            self,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    def clear_events(self) -> AggregateRoot:
        return replace(self, domain_events=())
