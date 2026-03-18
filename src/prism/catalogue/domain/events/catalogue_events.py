"""
Catalogue Domain Events

Architectural Intent:
- Immutable event records emitted on Product lifecycle state transitions
- Consumed by Discovery (re-index), Intelligence (analytics), and Try-On (asset prep)
- All events are tenant-scoped via inherited tenant_id for multi-tenant routing
- Carried on AggregateRoot.domain_events and dispatched after persistence

Event Flow:
  Ingest -> ProductIngestedEvent
  Enrich -> ProductEnrichedEvent
  Quality update -> CatalogueQualityUpdatedEvent
  Review -> ProductReviewedEvent
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class ProductIngestedEvent(DomainEvent):
    """
    Emitted when a new product is ingested from UCP or manual entry.

    Triggers downstream enrichment workflows and initial quality assessment.
    """

    sku: str = ""
    brand: str = ""
    source: str = ""  # e.g. "ucp", "manual", "bulk_import"


@dataclass(frozen=True)
class ProductEnrichedEvent(DomainEvent):
    """
    Emitted when AI enrichment completes on a product.

    Carries the enrichment delta so downstream consumers can react to
    specific attribute changes without re-fetching the full product.
    """

    sku: str = ""
    enriched_fields: tuple[str, ...] = ()
    quality_score_before: float = 0.0
    quality_score_after: float = 0.0


@dataclass(frozen=True)
class ProductReviewedEvent(DomainEvent):
    """
    Emitted when a human reviewer approves enriched product data.

    Marks the product as production-ready for storefront and discovery indexing.
    """

    sku: str = ""
    reviewer_id: str = ""


@dataclass(frozen=True)
class CatalogueQualityUpdatedEvent(DomainEvent):
    """
    Emitted when the aggregate quality score for a tenant's catalogue changes.

    Used by Intelligence context to track data quality trends over time.
    """

    previous_score: float = 0.0
    new_score: float = 0.0
    product_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
