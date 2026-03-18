"""
Shared Infrastructure — Event Bus Implementation

Architectural Intent:
- Implements EventBusPort from the domain layer
- Production implementation uses Google Cloud Pub/Sub
- In-memory implementation for testing
- Domain events are serialised to JSON for transport
- Tenant-scoped topic routing for multi-tenant isolation

MCP Integration:
- Can be exposed as an MCP server for cross-context event consumption
- Events published via MCP tool calls in the MCPEventBusAdapter pattern
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Any, Callable, Coroutine

from prism.shared.domain.events import DomainEvent, EventHandler


class _DateTimeEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class InMemoryEventBus:
    """In-memory event bus for testing and development."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._published: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        for event in events:
            self._published.append(event)
            handlers = self._handlers.get(event.event_type, [])
            await asyncio.gather(*(h.handle(event) for h in handlers))

    async def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:
        self._handlers[event_type.__name__].append(handler)

    @property
    def published_events(self) -> list[DomainEvent]:
        return list(self._published)


class PubSubEventBus:
    """
    Google Cloud Pub/Sub event bus implementation.

    Each event type maps to a Pub/Sub topic. Tenant ID is included
    as a message attribute for subscription-level filtering.
    """

    def __init__(self, project_id: str, topic_prefix: str = "prism") -> None:
        self._project_id = project_id
        self._topic_prefix = topic_prefix
        self._publisher: Any = None

    async def _get_publisher(self) -> Any:
        if self._publisher is None:
            from google.cloud.pubsub_v1 import PublisherClient

            self._publisher = PublisherClient()
        return self._publisher

    def _topic_path(self, event_type: str) -> str:
        return f"projects/{self._project_id}/topics/{self._topic_prefix}-{event_type}"

    async def publish(self, events: list[DomainEvent]) -> None:
        publisher = await self._get_publisher()
        futures = []
        for event in events:
            topic = self._topic_path(event.event_type)
            data = json.dumps(asdict(event), cls=_DateTimeEncoder).encode("utf-8")
            future = publisher.publish(
                topic,
                data,
                event_type=event.event_type,
                tenant_id=event.tenant_id,
                aggregate_id=event.aggregate_id,
            )
            futures.append(future)
        for future in futures:
            future.result()

    async def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:
        raise NotImplementedError(
            "Pub/Sub subscriptions are configured via infrastructure, not runtime"
        )
