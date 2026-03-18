"""
Intelligence Application DTOs — Data Transfer Objects

Architectural Intent:
- Pydantic models for serialisation at application boundaries
- DTOs decouple domain entities from API/MCP response shapes
- Factory methods convert from domain entities to DTOs
- All DTOs are immutable (Pydantic model_config frozen)
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from prism.intelligence.domain.entities.enrichment_job import EnrichmentJob
from prism.intelligence.domain.entities.quality_report import QualityReport


class EnrichmentJobDTO(BaseModel):
    """DTO representing an enrichment job's current state."""

    model_config = ConfigDict(frozen=True)

    id: str
    product_id: str
    tenant_id: str
    status: str
    extracted_attributes: dict[str, str] = Field(default_factory=dict)
    generated_description: str = ""
    embedding_vector_id: str = ""
    confidence_scores: dict[str, float] = Field(default_factory=dict)
    error_message: str | None = None
    model_version: str = ""
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_entity(job: EnrichmentJob) -> EnrichmentJobDTO:
        """Create a DTO from an EnrichmentJob domain entity."""
        return EnrichmentJobDTO(
            id=job.id,
            product_id=job.product_id,
            tenant_id=job.tenant_id.value,
            status=job.status.value,
            extracted_attributes=dict(job.extracted_attributes),
            generated_description=job.generated_description,
            embedding_vector_id=job.embedding_vector_id,
            confidence_scores=dict(job.confidence_scores),
            error_message=job.error_message,
            model_version=job.model_version,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class QualityReportDTO(BaseModel):
    """DTO representing a product quality assessment report."""

    model_config = ConfigDict(frozen=True)

    id: str
    product_id: str
    tenant_id: str
    completeness_score: float
    image_quality_score: float
    description_richness_score: float
    overall_score: float
    is_acceptable: bool
    needs_attention: bool
    recommendations: list[str] = Field(default_factory=list)
    created_at: datetime

    @staticmethod
    def from_entity(report: QualityReport) -> QualityReportDTO:
        """Create a DTO from a QualityReport domain entity."""
        return QualityReportDTO(
            id=report.id,
            product_id=report.product_id,
            tenant_id=report.tenant_id.value,
            completeness_score=report.completeness_score,
            image_quality_score=report.image_quality_score,
            description_richness_score=report.description_richness_score,
            overall_score=report.overall_score,
            is_acceptable=report.is_acceptable,
            needs_attention=report.needs_attention,
            recommendations=list(report.recommendations),
            created_at=report.created_at,
        )


class BatchEnrichmentResultDTO(BaseModel):
    """DTO summarising the outcome of a batch enrichment operation."""

    model_config = ConfigDict(frozen=True)

    total_requested: int = 0
    total_succeeded: int = 0
    total_failed: int = 0
    job_results: list[EnrichmentJobDTO] = Field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Percentage of successfully enriched products."""
        if self.total_requested == 0:
            return 0.0
        return self.total_succeeded / self.total_requested
