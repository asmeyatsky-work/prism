"""
Intelligence Domain Events — Enrichment Lifecycle and Quality Reporting

Architectural Intent:
- Each event marks a state transition in the enrichment pipeline
- Events carry enough data for downstream consumers to act without querying back
- All events are tenant-scoped via the base DomainEvent.tenant_id field
- Events are collected on the EnrichmentJob aggregate and dispatched after persistence
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from prism.shared.domain.events import DomainEvent


@dataclass(frozen=True)
class EnrichmentStartedEvent(DomainEvent):
    """Raised when an enrichment job begins processing a product."""

    product_id: str = ""
    model_version: str = ""


@dataclass(frozen=True)
class AttributesExtractedEvent(DomainEvent):
    """Raised when AI attribute extraction completes for a product."""

    product_id: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence_scores: dict[str, float] = field(default_factory=dict)
    requires_human_review: bool = False


@dataclass(frozen=True)
class DescriptionGeneratedEvent(DomainEvent):
    """Raised when a brand-voice description has been generated."""

    product_id: str = ""
    description_text: str = ""
    locale: str = "en"
    word_count: int = 0


@dataclass(frozen=True)
class EmbeddingCreatedEvent(DomainEvent):
    """Raised when embeddings have been generated and indexed."""

    product_id: str = ""
    vector_id: str = ""
    dimensions: int = 0
    model_name: str = ""


@dataclass(frozen=True)
class EnrichmentCompletedEvent(DomainEvent):
    """Raised when all enrichment stages complete successfully."""

    product_id: str = ""
    model_version: str = ""
    stages_completed: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnrichmentFailedEvent(DomainEvent):
    """Raised when the enrichment pipeline fails at any stage."""

    product_id: str = ""
    failed_stage: str = ""
    error_message: str = ""
    is_retriable: bool = True


@dataclass(frozen=True)
class QualityReportGeneratedEvent(DomainEvent):
    """Raised when a quality assessment report is produced for a product."""

    product_id: str = ""
    overall_score: float = 0.0
    recommendation_count: int = 0
