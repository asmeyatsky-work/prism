"""
Try-On Domain Events

Architectural Intent:
- Immutable event records emitted on TryOnSession lifecycle state transitions
- Consumed by Intelligence (analytics), Commerce (engagement tracking)
- All events are tenant-scoped via inherited tenant_id for multi-tenant routing
- Carried on AggregateRoot.domain_events and dispatched after persistence

Event Flow:
  Start -> TryOnStartedEvent
  Complete -> TryOnCompletedEvent
  Fail -> TryOnFailedEvent
  Outfit composed -> OutfitComposedEvent

Privacy:
- Events NEVER carry raw image data or customer PII
- Only session references, product IDs, and processing metrics
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class TryOnStartedEvent(DomainEvent):
    """
    Emitted when a virtual try-on session begins processing.

    Triggers latency tracking and resource allocation monitoring.
    """

    session_id: str = ""
    product_id: str = ""
    category: str = ""


@dataclass(frozen=True)
class TryOnCompletedEvent(DomainEvent):
    """
    Emitted when a virtual try-on session completes successfully.

    Carries performance metrics for SLA monitoring and model quality tracking.
    No customer image data is included — only the result reference.
    """

    session_id: str = ""
    product_id: str = ""
    processing_time_ms: int = 0
    confidence: float = 0.0
    result_image_url: str = ""


@dataclass(frozen=True)
class TryOnFailedEvent(DomainEvent):
    """
    Emitted when a virtual try-on session fails.

    Carries the failure reason for alerting and root-cause analysis.
    """

    session_id: str = ""
    product_id: str = ""
    reason: str = ""
    processing_time_ms: int = 0


@dataclass(frozen=True)
class OutfitComposedEvent(DomainEvent):
    """
    Emitted when an outfit composition (Complete the Look) is generated.

    Tracks outfit suggestion engagement for recommendation model improvement.
    """

    session_id: str = ""
    product_ids: tuple[str, ...] = ()
    style_score: float = 0.0
    occasion: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
