"""
Commerce Domain Entity — CommerceEvent Aggregate Root

Architectural Intent:
- CommerceEvent is the central aggregate for all commerce event processing
- Implements a state machine: RECEIVED -> PROCESSING -> PROCESSED | FAILED -> DEAD_LETTER
- Immutable (frozen dataclass) — state transitions return new instances
- Domain events are collected on state transitions for downstream dispatch
- Retry logic is bounded: events exceeding max retries are dead-lettered

State Machine:
  RECEIVED ──> PROCESSING ──> PROCESSED
                   │
                   └──> FAILED ──> (retry) ──> PROCESSING
                          │
                          └──> DEAD_LETTER (max retries exceeded)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from prism.shared.domain.entities import AggregateRoot
from prism.shared.domain.value_objects import TenantId


class CommerceEventType(str, Enum):
    """Types of commerce events flowing through the UCP connector."""

    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_UPDATED = "PRODUCT_UPDATED"
    INVENTORY_CHANGED = "INVENTORY_CHANGED"
    PRICE_CHANGED = "PRICE_CHANGED"
    ORDER_PLACED = "ORDER_PLACED"


class CommerceEventSource(str, Enum):
    """Source systems that can produce commerce events."""

    UCP = "UCP"
    PRISM = "PRISM"
    GOOGLE_SHOPPING = "GOOGLE_SHOPPING"


class ProcessingStatus(str, Enum):
    """Processing lifecycle status for a commerce event."""

    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


# Maximum number of retry attempts before dead-lettering
_MAX_RETRIES = 5


@dataclass(frozen=True)
class CommerceEvent(AggregateRoot):
    """
    Aggregate root for commerce event processing.

    Tracks the full lifecycle of a UCP event as it flows through PRISM's
    commerce pipeline: receive, classify, process, enrich, and push.

    Attributes:
        event_type: Classified type of the commerce event.
        source: System that produced the event.
        tenant_id: Multi-tenant scope.
        payload: Raw event payload preserved for reprocessing.
        processing_status: Current state in the processing lifecycle.
        retry_count: Number of processing retry attempts.
        failure_reason: Human-readable reason for the last failure.
    """

    event_type: CommerceEventType = CommerceEventType.PRODUCT_CREATED
    source: CommerceEventSource = CommerceEventSource.UCP
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    payload: tuple[tuple[str, Any], ...] = ()
    processing_status: ProcessingStatus = ProcessingStatus.RECEIVED
    retry_count: int = 0
    failure_reason: str = ""

    @property
    def payload_dict(self) -> dict[str, Any]:
        """Access payload as a mutable dict for processing."""
        return dict(self.payload)

    @property
    def is_terminal(self) -> bool:
        """Whether the event is in a terminal state (processed or dead-lettered)."""
        return self.processing_status in (
            ProcessingStatus.PROCESSED,
            ProcessingStatus.DEAD_LETTER,
        )

    @property
    def can_retry(self) -> bool:
        """Whether the event is eligible for retry."""
        return (
            self.processing_status == ProcessingStatus.FAILED
            and self.retry_count < _MAX_RETRIES
        )

    def mark_processing(self) -> CommerceEvent:
        """
        Transition to PROCESSING state.

        Valid from: RECEIVED, FAILED (retry).
        Raises ValueError if transition is invalid.
        """
        valid_from = (ProcessingStatus.RECEIVED, ProcessingStatus.FAILED)
        if self.processing_status not in valid_from:
            raise ValueError(
                f"Cannot transition to PROCESSING from {self.processing_status.value}"
            )
        from prism.commerce.domain.events.commerce_events import UCPEventReceivedEvent

        event = UCPEventReceivedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            event_type_name=self.event_type.value,
            source_name=self.source.value,
        )
        updated = replace(
            self,
            processing_status=ProcessingStatus.PROCESSING,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=updated.domain_events + (event,),
        )

    def mark_processed(self) -> CommerceEvent:
        """
        Transition to PROCESSED terminal state.

        Valid from: PROCESSING only.
        """
        if self.processing_status != ProcessingStatus.PROCESSING:
            raise ValueError(
                f"Cannot transition to PROCESSED from {self.processing_status.value}"
            )
        return replace(
            self,
            processing_status=ProcessingStatus.PROCESSED,
            failure_reason="",
            **self._touch(),
        )

    def mark_failed(self, reason: str) -> CommerceEvent:
        """
        Transition to FAILED state with a reason.

        Valid from: PROCESSING only. Increments retry_count.
        If max retries exceeded, automatically dead-letters.
        """
        if self.processing_status != ProcessingStatus.PROCESSING:
            raise ValueError(
                f"Cannot transition to FAILED from {self.processing_status.value}"
            )
        new_retry_count = self.retry_count + 1
        if new_retry_count >= _MAX_RETRIES:
            return self._dead_letter(reason)
        return replace(
            self,
            processing_status=ProcessingStatus.FAILED,
            retry_count=new_retry_count,
            failure_reason=reason,
            **self._touch(),
        )

    def send_to_dead_letter(self) -> CommerceEvent:
        """
        Explicitly transition to DEAD_LETTER state.

        Valid from: FAILED or PROCESSING.
        """
        valid_from = (ProcessingStatus.FAILED, ProcessingStatus.PROCESSING)
        if self.processing_status not in valid_from:
            raise ValueError(
                f"Cannot transition to DEAD_LETTER from {self.processing_status.value}"
            )
        return self._dead_letter(self.failure_reason or "Manually dead-lettered")

    def _dead_letter(self, reason: str) -> CommerceEvent:
        """Internal helper to transition to DEAD_LETTER and emit domain event."""
        from prism.commerce.domain.events.commerce_events import (
            CommerceEventDeadLetteredEvent,
        )

        event = CommerceEventDeadLetteredEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            event_type_name=self.event_type.value,
            failure_reason=reason,
            retry_count=self.retry_count,
        )
        updated = replace(
            self,
            processing_status=ProcessingStatus.DEAD_LETTER,
            failure_reason=reason,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=updated.domain_events + (event,),
        )
