"""
Tests for CommerceEvent Aggregate — Domain State Machine

Verifies the complete state machine:
  RECEIVED -> PROCESSING -> PROCESSED
  RECEIVED -> PROCESSING -> FAILED -> PROCESSING (retry) -> PROCESSED
  RECEIVED -> PROCESSING -> FAILED (max retries) -> DEAD_LETTER
  Invalid transitions raise ValueError
"""

from __future__ import annotations

import pytest

from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventSource,
    CommerceEventType,
    ProcessingStatus,
    _MAX_RETRIES,
)
from prism.commerce.domain.events.commerce_events import (
    CommerceEventDeadLetteredEvent,
    UCPEventReceivedEvent,
)
from prism.shared.domain.value_objects import TenantId


@pytest.fixture
def received_event() -> CommerceEvent:
    """Create a CommerceEvent in RECEIVED status."""
    return CommerceEvent(
        event_type=CommerceEventType.PRODUCT_CREATED,
        source=CommerceEventSource.UCP,
        tenant_id=TenantId(value="tenant-gucci"),
        payload=(("sku", "GUC-001"), ("name", "Bamboo Bag")),
        processing_status=ProcessingStatus.RECEIVED,
    )


class TestCommerceEventCreation:
    """Tests for CommerceEvent construction and properties."""

    def test_create_with_defaults(self) -> None:
        event = CommerceEvent()
        assert event.processing_status == ProcessingStatus.RECEIVED
        assert event.retry_count == 0
        assert event.failure_reason == ""
        assert event.domain_events == ()
        assert event.is_terminal is False

    def test_create_with_all_fields(self) -> None:
        tid = TenantId(value="tenant-hermes")
        event = CommerceEvent(
            event_type=CommerceEventType.INVENTORY_CHANGED,
            source=CommerceEventSource.PRISM,
            tenant_id=tid,
            payload=(("product_id", "HRM-001"),),
            processing_status=ProcessingStatus.RECEIVED,
        )
        assert event.event_type == CommerceEventType.INVENTORY_CHANGED
        assert event.source == CommerceEventSource.PRISM
        assert event.tenant_id == tid
        assert event.payload_dict == {"product_id": "HRM-001"}

    def test_immutability(self, received_event: CommerceEvent) -> None:
        with pytest.raises(AttributeError):
            received_event.processing_status = ProcessingStatus.PROCESSING  # type: ignore[misc]


class TestCommerceEventStateTransitions:
    """Tests for the processing state machine."""

    def test_received_to_processing(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        assert processing.processing_status == ProcessingStatus.PROCESSING
        assert len(processing.domain_events) == 1
        assert isinstance(processing.domain_events[0], UCPEventReceivedEvent)

    def test_processing_to_processed(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        processed = processing.mark_processed()
        assert processed.processing_status == ProcessingStatus.PROCESSED
        assert processed.is_terminal is True
        assert processed.failure_reason == ""

    def test_processing_to_failed(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        failed = processing.mark_failed("Connection timeout")
        assert failed.processing_status == ProcessingStatus.FAILED
        assert failed.retry_count == 1
        assert failed.failure_reason == "Connection timeout"
        assert failed.is_terminal is False

    def test_failed_to_processing_retry(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        failed = processing.mark_failed("Transient error")
        assert failed.can_retry is True
        retried = failed.mark_processing()
        assert retried.processing_status == ProcessingStatus.PROCESSING

    def test_retry_to_processed(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        failed = processing.mark_failed("Transient error")
        retried = failed.mark_processing()
        processed = retried.mark_processed()
        assert processed.processing_status == ProcessingStatus.PROCESSED
        assert processed.retry_count == 1

    def test_max_retries_triggers_dead_letter(self, received_event: CommerceEvent) -> None:
        event = received_event
        for i in range(_MAX_RETRIES - 1):
            event = event.mark_processing()
            event = event.mark_failed(f"Failure {i + 1}")
        # One more failure should dead-letter
        event = event.mark_processing()
        dead_lettered = event.mark_failed(f"Failure {_MAX_RETRIES}")
        assert dead_lettered.processing_status == ProcessingStatus.DEAD_LETTER
        assert dead_lettered.is_terminal is True
        # Should have a dead-letter domain event
        dl_events = [
            e for e in dead_lettered.domain_events
            if isinstance(e, CommerceEventDeadLetteredEvent)
        ]
        assert len(dl_events) >= 1

    def test_explicit_dead_letter_from_failed(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        failed = processing.mark_failed("Bad data")
        dead_lettered = failed.send_to_dead_letter()
        assert dead_lettered.processing_status == ProcessingStatus.DEAD_LETTER

    def test_explicit_dead_letter_from_processing(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        dead_lettered = processing.send_to_dead_letter()
        assert dead_lettered.processing_status == ProcessingStatus.DEAD_LETTER


class TestCommerceEventInvalidTransitions:
    """Tests for invalid state transitions."""

    def test_cannot_process_from_processed(self, received_event: CommerceEvent) -> None:
        processed = received_event.mark_processing().mark_processed()
        with pytest.raises(ValueError, match="Cannot transition to PROCESSING from PROCESSED"):
            processed.mark_processing()

    def test_cannot_mark_processed_from_received(self, received_event: CommerceEvent) -> None:
        with pytest.raises(ValueError, match="Cannot transition to PROCESSED from RECEIVED"):
            received_event.mark_processed()

    def test_cannot_fail_from_received(self, received_event: CommerceEvent) -> None:
        with pytest.raises(ValueError, match="Cannot transition to FAILED from RECEIVED"):
            received_event.mark_failed("Should not work")

    def test_cannot_dead_letter_from_received(self, received_event: CommerceEvent) -> None:
        with pytest.raises(ValueError, match="Cannot transition to DEAD_LETTER from RECEIVED"):
            received_event.send_to_dead_letter()

    def test_cannot_dead_letter_from_processed(self, received_event: CommerceEvent) -> None:
        processed = received_event.mark_processing().mark_processed()
        with pytest.raises(ValueError, match="Cannot transition to DEAD_LETTER from PROCESSED"):
            processed.send_to_dead_letter()


class TestCommerceEventDomainEvents:
    """Tests for domain event emission during state transitions."""

    def test_mark_processing_emits_ucp_event_received(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        assert len(processing.domain_events) == 1
        event = processing.domain_events[0]
        assert isinstance(event, UCPEventReceivedEvent)
        assert event.aggregate_id == processing.id
        assert event.tenant_id == "tenant-gucci"
        assert event.event_type_name == "PRODUCT_CREATED"
        assert event.source_name == "UCP"

    def test_dead_letter_emits_dead_lettered_event(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        dead_lettered = processing.send_to_dead_letter()
        dl_events = [
            e for e in dead_lettered.domain_events
            if isinstance(e, CommerceEventDeadLetteredEvent)
        ]
        assert len(dl_events) == 1
        assert dl_events[0].failure_reason == "Manually dead-lettered"

    def test_clear_events(self, received_event: CommerceEvent) -> None:
        processing = received_event.mark_processing()
        assert len(processing.domain_events) > 0
        cleared = processing.clear_events()
        assert cleared.domain_events == ()
