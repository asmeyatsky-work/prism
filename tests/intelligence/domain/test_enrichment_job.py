"""
Tests for EnrichmentJob Aggregate Root — State Machine Transitions

Tests verify:
- Happy path: PENDING -> EXTRACTING -> GENERATING -> EMBEDDING -> COMPLETED
- Each transition produces the correct domain event
- Invalid transitions raise ValueError
- Fail transitions work from any non-terminal state
- Immutability is preserved (each transition returns a new instance)
"""

from __future__ import annotations

import pytest

from prism.intelligence.domain.entities.enrichment_job import EnrichmentJob, EnrichmentStatus
from prism.intelligence.domain.events.intelligence_events import (
    AttributesExtractedEvent,
    DescriptionGeneratedEvent,
    EmbeddingCreatedEvent,
    EnrichmentCompletedEvent,
    EnrichmentFailedEvent,
    EnrichmentStartedEvent,
)
from prism.shared.domain.value_objects import TenantId


@pytest.fixture
def tenant_id() -> TenantId:
    """Standard test tenant."""
    return TenantId(value="tenant-gucci")


@pytest.fixture
def job(tenant_id: TenantId) -> EnrichmentJob:
    """A fresh enrichment job in PENDING state."""
    return EnrichmentJob(
        product_id="prod-001",
        tenant_id=tenant_id,
        model_version="v1.0",
    )


class TestEnrichmentJobStateTransitions:
    """Test the full enrichment state machine."""

    def test_initial_state_is_pending(self, job: EnrichmentJob) -> None:
        assert job.status == EnrichmentStatus.PENDING
        assert job.product_id == "prod-001"
        assert job.tenant_id.value == "tenant-gucci"
        assert job.model_version == "v1.0"
        assert job.domain_events == ()

    def test_start_extraction(self, job: EnrichmentJob) -> None:
        updated = job.start_extraction()

        assert updated.status == EnrichmentStatus.EXTRACTING_ATTRIBUTES
        assert len(updated.domain_events) == 1
        event = updated.domain_events[0]
        assert isinstance(event, EnrichmentStartedEvent)
        assert event.product_id == "prod-001"
        assert event.tenant_id == "tenant-gucci"
        assert event.model_version == "v1.0"

    def test_complete_extraction(self, job: EnrichmentJob) -> None:
        extracting = job.start_extraction()
        attributes = {"material": "cashmere", "colour": "ivory"}
        confidence = {"material": 0.95, "colour": 0.88}

        updated = extracting.complete_extraction(attributes, confidence)

        assert updated.status == EnrichmentStatus.GENERATING_DESCRIPTION
        assert updated.extracted_attributes == attributes
        assert updated.confidence_scores == confidence
        assert len(updated.domain_events) == 2
        assert isinstance(updated.domain_events[1], AttributesExtractedEvent)

    def test_complete_description(self, job: EnrichmentJob) -> None:
        desc_text = "A sumptuous cashmere piece in ivory."
        updated = (
            job.start_extraction()
            .complete_extraction({"material": "cashmere"}, {"material": 0.95})
            .complete_description(desc_text)
        )

        assert updated.status == EnrichmentStatus.EMBEDDING
        assert updated.generated_description == desc_text
        assert len(updated.domain_events) == 3
        desc_event = updated.domain_events[2]
        assert isinstance(desc_event, DescriptionGeneratedEvent)
        assert desc_event.description_text == desc_text
        assert desc_event.word_count == 7

    def test_complete_embedding(self, job: EnrichmentJob) -> None:
        updated = (
            job.start_extraction()
            .complete_extraction({"material": "silk"}, {"material": 0.9})
            .complete_description("Pure silk elegance.")
            .complete_embedding("vec-001")
        )

        assert updated.status == EnrichmentStatus.COMPLETED
        assert updated.embedding_vector_id == "vec-001"
        # Should have 5 events: started, extracted, description, embedding, completed
        assert len(updated.domain_events) == 5
        assert isinstance(updated.domain_events[3], EmbeddingCreatedEvent)
        assert isinstance(updated.domain_events[4], EnrichmentCompletedEvent)

    def test_full_pipeline_produces_correct_event_sequence(
        self, job: EnrichmentJob
    ) -> None:
        completed = (
            job.start_extraction()
            .complete_extraction({"material": "leather"}, {"material": 0.92})
            .complete_description("Finest Italian leather.")
            .complete_embedding("vec-002")
        )

        event_types = [type(e).__name__ for e in completed.domain_events]
        assert event_types == [
            "EnrichmentStartedEvent",
            "AttributesExtractedEvent",
            "DescriptionGeneratedEvent",
            "EmbeddingCreatedEvent",
            "EnrichmentCompletedEvent",
        ]


class TestEnrichmentJobInvalidTransitions:
    """Test that invalid state transitions raise ValueError."""

    def test_cannot_start_extraction_twice(self, job: EnrichmentJob) -> None:
        extracting = job.start_extraction()
        with pytest.raises(ValueError, match="expected status 'PENDING'"):
            extracting.start_extraction()

    def test_cannot_complete_extraction_from_pending(
        self, job: EnrichmentJob
    ) -> None:
        with pytest.raises(ValueError, match="expected status 'EXTRACTING_ATTRIBUTES'"):
            job.complete_extraction({}, {})

    def test_cannot_complete_description_from_pending(
        self, job: EnrichmentJob
    ) -> None:
        with pytest.raises(ValueError, match="expected status 'GENERATING_DESCRIPTION'"):
            job.complete_description("text")

    def test_cannot_complete_embedding_from_pending(
        self, job: EnrichmentJob
    ) -> None:
        with pytest.raises(ValueError, match="expected status 'EMBEDDING'"):
            job.complete_embedding("vec")

    def test_cannot_skip_extraction(self, job: EnrichmentJob) -> None:
        with pytest.raises(ValueError):
            job.complete_description("skip ahead")


class TestEnrichmentJobFailure:
    """Test failure transitions from various states."""

    def test_fail_from_pending(self, job: EnrichmentJob) -> None:
        failed = job.fail("Image not found")

        assert failed.status == EnrichmentStatus.FAILED
        assert failed.error_message == "Image not found"
        assert len(failed.domain_events) == 1
        event = failed.domain_events[0]
        assert isinstance(event, EnrichmentFailedEvent)
        assert event.error_message == "Image not found"
        assert event.failed_stage == "PENDING"

    def test_fail_from_extracting(self, job: EnrichmentJob) -> None:
        extracting = job.start_extraction()
        failed = extracting.fail("Vision API timeout")

        assert failed.status == EnrichmentStatus.FAILED
        assert failed.error_message == "Vision API timeout"
        # Should have 2 events: started + failed
        assert len(failed.domain_events) == 2

    def test_fail_from_embedding(self, job: EnrichmentJob) -> None:
        embedding = (
            job.start_extraction()
            .complete_extraction({"material": "wool"}, {"material": 0.8})
            .complete_description("Fine wool.")
        )
        failed = embedding.fail("Vector index unavailable")

        assert failed.status == EnrichmentStatus.FAILED
        assert "Vector index unavailable" in (failed.error_message or "")

    def test_cannot_fail_from_completed(self, job: EnrichmentJob) -> None:
        completed = (
            job.start_extraction()
            .complete_extraction({"material": "silk"}, {"material": 0.9})
            .complete_description("Silk.")
            .complete_embedding("vec-001")
        )
        with pytest.raises(ValueError, match="terminal status"):
            completed.fail("too late")

    def test_cannot_fail_from_already_failed(self, job: EnrichmentJob) -> None:
        failed = job.fail("first failure")
        with pytest.raises(ValueError, match="terminal status"):
            failed.fail("second failure")


class TestEnrichmentJobImmutability:
    """Test that all transitions return new instances without mutating the original."""

    def test_start_extraction_returns_new_instance(
        self, job: EnrichmentJob
    ) -> None:
        updated = job.start_extraction()
        assert job is not updated
        assert job.status == EnrichmentStatus.PENDING
        assert updated.status == EnrichmentStatus.EXTRACTING_ATTRIBUTES

    def test_complete_extraction_returns_new_instance(
        self, job: EnrichmentJob
    ) -> None:
        extracting = job.start_extraction()
        updated = extracting.complete_extraction({"colour": "red"}, {"colour": 0.9})
        assert extracting is not updated
        assert extracting.extracted_attributes == {}
        assert updated.extracted_attributes == {"colour": "red"}

    def test_fail_returns_new_instance(self, job: EnrichmentJob) -> None:
        failed = job.fail("error")
        assert job is not failed
        assert job.status == EnrichmentStatus.PENDING
        assert failed.status == EnrichmentStatus.FAILED

    def test_clear_events_returns_new_instance(self, job: EnrichmentJob) -> None:
        with_events = job.start_extraction()
        cleared = with_events.clear_events()
        assert with_events is not cleared
        assert len(with_events.domain_events) == 1
        assert len(cleared.domain_events) == 0
