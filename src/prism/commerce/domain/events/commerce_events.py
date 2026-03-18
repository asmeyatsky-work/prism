"""
Commerce Domain Events

Architectural Intent:
- Immutable event records emitted during commerce event processing lifecycle
- Consumed by Intelligence (analytics), Catalogue (product sync), and Discovery (re-index)
- All events are tenant-scoped via inherited tenant_id for multi-tenant Pub/Sub routing
- Carried on AggregateRoot.domain_events and dispatched after persistence

Event Flow:
  UCP event received    -> UCPEventReceivedEvent
  Inventory updated     -> InventoryUpdatedEvent
  Feed synced           -> GoogleShoppingFeedSyncedEvent
  Enriched data pushed  -> EnrichedProductPushedEvent
  Processing failed     -> CommerceEventDeadLetteredEvent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class UCPEventReceivedEvent(DomainEvent):
    """
    Emitted when a UCP event is received and begins processing.

    Triggers downstream classification, enrichment, and inventory workflows.
    """

    event_type_name: str = ""
    source_name: str = ""


@dataclass(frozen=True)
class InventoryUpdatedEvent(DomainEvent):
    """
    Emitted when an inventory signal is updated for a product.

    Consumed by Discovery context to update availability filters
    and by Google Shopping feed to reflect stock status.
    """

    product_id: str = ""
    location: str = ""
    available_quantity: int = 0
    fulfilment_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class GoogleShoppingFeedSyncedEvent(DomainEvent):
    """
    Emitted when a Google Shopping feed sync completes (success or error).

    Consumed by Intelligence context for feed health monitoring.
    """

    feed_id: str = ""
    product_count: int = 0
    quality_score: float = 0.0
    sync_status: str = ""


@dataclass(frozen=True)
class EnrichedProductPushedEvent(DomainEvent):
    """
    Emitted when PRISM-enriched product data is pushed back to UCP.

    Confirms that the UCP has been updated with AI-generated attributes,
    taxonomy codes, and quality improvements.
    """

    product_id: str = ""
    sku: str = ""
    enrichment_version: str = ""
    quality_score: float = 0.0


@dataclass(frozen=True)
class CommerceEventDeadLetteredEvent(DomainEvent):
    """
    Emitted when a commerce event exhausts retries and is dead-lettered.

    Triggers alerting and manual investigation workflows.
    Critical for operational monitoring of the commerce pipeline.
    """

    event_type_name: str = ""
    failure_reason: str = ""
    retry_count: int = 0
