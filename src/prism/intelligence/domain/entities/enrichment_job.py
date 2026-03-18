"""
Intelligence Domain Entity — EnrichmentJob Aggregate Root

Architectural Intent:
- EnrichmentJob is the central aggregate for the AI enrichment pipeline
- Implements a state machine: PENDING -> EXTRACTING -> GENERATING -> EMBEDDING -> COMPLETED
- Each state transition produces a domain event and returns a new immutable instance
- Frozen dataclass enforces immutability per skill2026 Rule 3
- Tenant-scoped via TenantId value object

State Machine:
    PENDING ──> EXTRACTING_ATTRIBUTES ──> GENERATING_DESCRIPTION ──> EMBEDDING ──> COMPLETED
       │              │                         │                       │
       └──────────────┴─────────────────────────┴───────────────────────┴──> FAILED
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum

from prism.intelligence.domain.events.intelligence_events import (
    AttributesExtractedEvent,
    DescriptionGeneratedEvent,
    EmbeddingCreatedEvent,
    EnrichmentCompletedEvent,
    EnrichmentFailedEvent,
    EnrichmentStartedEvent,
)
from prism.shared.domain.entities import AggregateRoot
from prism.shared.domain.value_objects import TenantId


class EnrichmentStatus(str, Enum):
    """State machine states for the enrichment pipeline."""

    PENDING = "PENDING"
    EXTRACTING_ATTRIBUTES = "EXTRACTING_ATTRIBUTES"
    GENERATING_DESCRIPTION = "GENERATING_DESCRIPTION"
    EMBEDDING = "EMBEDDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class EnrichmentJob(AggregateRoot):
    """
    Aggregate root tracking the lifecycle of a product enrichment job.

    Each enrichment job processes a single product through the AI pipeline:
    attribute extraction, description generation, and embedding creation.
    State transitions are explicit and each produces a domain event for
    downstream consumers.
    """

    product_id: str = ""
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    status: EnrichmentStatus = EnrichmentStatus.PENDING
    extracted_attributes: dict[str, str] = field(default_factory=dict)
    generated_description: str = ""
    embedding_vector_id: str = ""
    confidence_scores: dict[str, float] = field(default_factory=dict)
    error_message: str | None = None
    model_version: str = ""

    def start_extraction(self) -> EnrichmentJob:
        """
        Transition from PENDING to EXTRACTING_ATTRIBUTES.

        Returns a new EnrichmentJob instance with updated status and
        an EnrichmentStartedEvent appended to domain events.

        Raises:
            ValueError: If the job is not in PENDING status.
        """
        self._assert_status(EnrichmentStatus.PENDING, "start_extraction")
        event = EnrichmentStartedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            model_version=self.model_version,
        )
        updated = replace(
            self,
            status=EnrichmentStatus.EXTRACTING_ATTRIBUTES,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=self.domain_events + (event,),
        )

    def complete_extraction(
        self,
        attributes: dict[str, str],
        confidence: dict[str, float],
    ) -> EnrichmentJob:
        """
        Complete attribute extraction and transition to GENERATING_DESCRIPTION.

        Args:
            attributes: Extracted product attributes keyed by attribute name.
            confidence: Confidence scores for each extracted attribute.

        Returns:
            New EnrichmentJob instance with extracted data and updated status.

        Raises:
            ValueError: If the job is not in EXTRACTING_ATTRIBUTES status.
        """
        self._assert_status(EnrichmentStatus.EXTRACTING_ATTRIBUTES, "complete_extraction")
        event = AttributesExtractedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            attributes=attributes,
            confidence_scores=confidence,
        )
        updated = replace(
            self,
            status=EnrichmentStatus.GENERATING_DESCRIPTION,
            extracted_attributes=attributes,
            confidence_scores=confidence,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=self.domain_events + (event,),
        )

    def start_description(self) -> EnrichmentJob:
        """
        Mark that description generation is actively in progress.

        This is an optional explicit signal; the status is already
        GENERATING_DESCRIPTION after complete_extraction. Useful for
        tracking when the generation call is actually dispatched.

        Returns:
            New EnrichmentJob instance (status unchanged, event emitted).

        Raises:
            ValueError: If the job is not in GENERATING_DESCRIPTION status.
        """
        self._assert_status(EnrichmentStatus.GENERATING_DESCRIPTION, "start_description")
        return replace(self, **self._touch())

    def complete_description(self, text: str) -> EnrichmentJob:
        """
        Complete description generation and transition to EMBEDDING.

        Args:
            text: The generated brand-voice product description.

        Returns:
            New EnrichmentJob instance with the description and updated status.

        Raises:
            ValueError: If the job is not in GENERATING_DESCRIPTION status.
        """
        self._assert_status(EnrichmentStatus.GENERATING_DESCRIPTION, "complete_description")
        event = DescriptionGeneratedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            description_text=text,
            word_count=len(text.split()),
        )
        updated = replace(
            self,
            status=EnrichmentStatus.EMBEDDING,
            generated_description=text,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=self.domain_events + (event,),
        )

    def start_embedding(self) -> EnrichmentJob:
        """
        Mark that embedding generation is actively in progress.

        Returns:
            New EnrichmentJob instance (status unchanged, event emitted).

        Raises:
            ValueError: If the job is not in EMBEDDING status.
        """
        self._assert_status(EnrichmentStatus.EMBEDDING, "start_embedding")
        return replace(self, **self._touch())

    def complete_embedding(self, vector_id: str) -> EnrichmentJob:
        """
        Complete embedding creation and transition to COMPLETED.

        Args:
            vector_id: The identifier of the stored embedding vector.

        Returns:
            New EnrichmentJob instance in COMPLETED status.

        Raises:
            ValueError: If the job is not in EMBEDDING status.
        """
        self._assert_status(EnrichmentStatus.EMBEDDING, "complete_embedding")
        embedding_event = EmbeddingCreatedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            vector_id=vector_id,
        )
        completed_event = EnrichmentCompletedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            model_version=self.model_version,
            stages_completed=(
                "extract_attributes",
                "generate_description",
                "generate_embedding",
            ),
        )
        updated = replace(
            self,
            status=EnrichmentStatus.COMPLETED,
            embedding_vector_id=vector_id,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=self.domain_events + (embedding_event, completed_event),
        )

    def fail(self, reason: str) -> EnrichmentJob:
        """
        Transition to FAILED from any non-terminal status.

        Args:
            reason: Human-readable failure reason for diagnostics.

        Returns:
            New EnrichmentJob instance in FAILED status with error details.

        Raises:
            ValueError: If the job is already COMPLETED or FAILED.
        """
        if self.status in (EnrichmentStatus.COMPLETED, EnrichmentStatus.FAILED):
            raise ValueError(
                f"Cannot fail enrichment job in terminal status '{self.status.value}'"
            )
        event = EnrichmentFailedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            product_id=self.product_id,
            failed_stage=self.status.value,
            error_message=reason,
            is_retriable=self.status != EnrichmentStatus.COMPLETED,
        )
        updated = replace(
            self,
            status=EnrichmentStatus.FAILED,
            error_message=reason,
            **self._touch(),
        )
        return replace(
            updated,
            domain_events=self.domain_events + (event,),
        )

    def _assert_status(self, expected: EnrichmentStatus, operation: str) -> None:
        """Raise ValueError if current status does not match expected."""
        if self.status != expected:
            raise ValueError(
                f"Cannot {operation}: expected status '{expected.value}', "
                f"got '{self.status.value}'"
            )
