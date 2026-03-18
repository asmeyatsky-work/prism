"""
Intelligence Application Command — Enrich Product Use Case

Architectural Intent:
- Orchestrates the full AI enrichment pipeline via DAGOrchestrator
- Parallel-first: attribute extraction and image quality run concurrently
- Sequential dependencies: description depends on attributes, embedding depends on both
- Each pipeline step delegates to a domain port (no infrastructure leakage)
- Domain events are collected on the aggregate and published after persistence

DAG Topology:
    extract_attributes ─────┐
                            ├──> generate_description ──> generate_embedding
    assess_image_quality ───┘
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from prism.intelligence.domain.entities.enrichment_job import EnrichmentJob, EnrichmentStatus
from prism.intelligence.domain.entities.quality_report import QualityReport
from prism.intelligence.domain.events.intelligence_events import QualityReportGeneratedEvent
from prism.intelligence.domain.ports.ai_ports import (
    AttributeExtractionPort,
    DescriptionGenerationPort,
    EmbeddingGenerationPort,
    VectorIndexPort,
)
from prism.intelligence.domain.ports.quality_ports import (
    ImageQualityPort,
    QualityReportRepositoryPort,
)
from prism.intelligence.domain.services.enrichment_service import EnrichmentService
from prism.intelligence.domain.value_objects.ai_output import ExtractedAttributes
from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig
from prism.shared.application.dtos import CommandResult, TenantContext
from prism.shared.application.orchestration import DAGOrchestrator, WorkflowStep
from prism.shared.domain.events import EventBusPort
from prism.shared.domain.ports import RepositoryPort
from prism.shared.domain.value_objects import ImageRef, Locale, TenantId


@dataclass(frozen=True)
class EnrichProductCommand:
    """Command to enrich a single product with AI-generated data."""

    product_id: str
    tenant_context: TenantContext
    images: list[ImageRef]
    voice_config: BrandVoiceConfig
    locale: Locale
    model_version: str = "v1"
    existing_attributes: dict[str, str] | None = None


class EnrichProductUseCase:
    """
    Orchestrates the full AI enrichment pipeline for a single product.

    Uses DAGOrchestrator for parallel-safe step execution:
    1. extract_attributes (parallel with assess_image_quality)
    2. generate_description (depends on extract_attributes)
    3. generate_embedding (depends on generate_description)

    Publishes domain events after successful persistence.
    """

    def __init__(
        self,
        job_repository: RepositoryPort[EnrichmentJob],
        quality_report_repository: QualityReportRepositoryPort,
        attribute_extractor: AttributeExtractionPort,
        description_generator: DescriptionGenerationPort,
        embedding_generator: EmbeddingGenerationPort,
        vector_index: VectorIndexPort,
        image_quality_assessor: ImageQualityPort,
        event_bus: EventBusPort,
        enrichment_service: EnrichmentService | None = None,
    ) -> None:
        self._job_repo = job_repository
        self._quality_repo = quality_report_repository
        self._extractor = attribute_extractor
        self._desc_gen = description_generator
        self._embed_gen = embedding_generator
        self._vector_index = vector_index
        self._image_quality = image_quality_assessor
        self._event_bus = event_bus
        self._enrichment_service = enrichment_service or EnrichmentService()

    async def execute(self, command: EnrichProductCommand) -> CommandResult[str]:
        """
        Execute the enrichment pipeline for a product.

        Args:
            command: Enrichment command with product data and configuration.

        Returns:
            CommandResult containing the enrichment job ID on success,
            or an error message on failure.
        """
        tenant_id = TenantId(value=command.tenant_context.tenant_id)

        # Create and persist the initial job
        job = EnrichmentJob(
            product_id=command.product_id,
            tenant_id=tenant_id,
            model_version=command.model_version,
        )

        try:
            # Start extraction phase
            job = job.start_extraction()
            await self._job_repo.save(job, tenant_id)

            # Build enrichment context for DAG steps
            context: dict[str, Any] = {
                "job": job,
                "command": command,
                "tenant_id": tenant_id,
            }

            # Define DAG steps
            steps = [
                WorkflowStep(
                    name="extract_attributes",
                    execute=self._step_extract_attributes,
                    depends_on=(),
                    is_critical=True,
                    timeout_seconds=60.0,
                ),
                WorkflowStep(
                    name="assess_image_quality",
                    execute=self._step_assess_image_quality,
                    depends_on=(),
                    is_critical=False,
                    timeout_seconds=30.0,
                ),
                WorkflowStep(
                    name="generate_description",
                    execute=self._step_generate_description,
                    depends_on=("extract_attributes",),
                    is_critical=True,
                    timeout_seconds=60.0,
                ),
                WorkflowStep(
                    name="generate_embedding",
                    execute=self._step_generate_embedding,
                    depends_on=("generate_description",),
                    is_critical=True,
                    timeout_seconds=30.0,
                ),
            ]

            orchestrator = DAGOrchestrator(steps)
            results = await orchestrator.execute(context)

            # Reconstruct final job state from step results
            job = results["generate_embedding"].value
            await self._job_repo.save(job, tenant_id)

            # Build quality report if image assessment succeeded
            if results.get("assess_image_quality") and results["assess_image_quality"].success:
                image_quality_score = results["assess_image_quality"].value
                quality_report = self._build_quality_report(
                    job=job,
                    tenant_id=tenant_id,
                    image_quality_score=image_quality_score,
                )
                await self._quality_repo.save(quality_report, tenant_id)

            # Publish all collected domain events
            await self._event_bus.publish(list(job.domain_events))

            return CommandResult.ok(job.id)

        except Exception as exc:
            # Transition to failed state and persist
            if job.status not in (EnrichmentStatus.COMPLETED, EnrichmentStatus.FAILED):
                job = job.fail(str(exc))
                await self._job_repo.save(job, tenant_id)
                await self._event_bus.publish(list(job.domain_events))
            return CommandResult.fail(str(exc), code="ENRICHMENT_FAILED")

    async def _step_extract_attributes(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> EnrichmentJob:
        """DAG step: Extract attributes from product images."""
        command: EnrichProductCommand = context["command"]
        job: EnrichmentJob = context["job"]

        extraction_context = {
            "brand": command.voice_config.brand_name,
            "locale": command.locale.code,
        }

        extracted: ExtractedAttributes = await self._extractor.extract_attributes(
            images=command.images,
            context=extraction_context,
        )

        attributes = extracted.to_flat_dict()
        confidence = extracted.confidence_scores()

        # Merge with existing attributes if provided
        if command.existing_attributes:
            attributes = self._enrichment_service.merge_attributes(
                existing=command.existing_attributes,
                extracted=attributes,
                confidence_scores=confidence,
            )

        job = job.complete_extraction(attributes=attributes, confidence=confidence)
        context["job"] = job
        return job

    async def _step_assess_image_quality(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> float:
        """DAG step: Assess image quality (non-critical, runs in parallel)."""
        command: EnrichProductCommand = context["command"]
        return await self._image_quality.assess_quality(command.images)

    async def _step_generate_description(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> EnrichmentJob:
        """DAG step: Generate brand-voice description from extracted attributes."""
        command: EnrichProductCommand = context["command"]
        job: EnrichmentJob = dep_results.get("extract_attributes", context["job"])

        description = await self._desc_gen.generate_description(
            attributes=dict(job.extracted_attributes),
            voice_config=command.voice_config,
            locale=command.locale,
        )

        job = job.complete_description(description.text)
        context["job"] = job
        return job

    async def _step_generate_embedding(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> EnrichmentJob:
        """DAG step: Generate embedding and index it in vector store."""
        job: EnrichmentJob = dep_results.get("generate_description", context["job"])

        # Combine attributes and description for embedding text
        attr_text = " ".join(
            f"{k}: {v}" for k, v in job.extracted_attributes.items() if v
        )
        embed_text = f"{attr_text} {job.generated_description}"

        vector = await self._embed_gen.generate_text_embedding(embed_text)
        vector_id = await self._vector_index.upsert(
            product_id=job.product_id,
            vector=vector,
        )

        job = job.complete_embedding(vector_id)
        context["job"] = job
        return job

    def _build_quality_report(
        self,
        job: EnrichmentJob,
        tenant_id: TenantId,
        image_quality_score: float,
    ) -> QualityReport:
        """Build a quality report from enrichment results."""
        # Completeness: proportion of non-empty attributes
        total_attrs = len(job.extracted_attributes)
        filled_attrs = sum(1 for v in job.extracted_attributes.values() if v)
        completeness = filled_attrs / total_attrs if total_attrs > 0 else 0.0

        # Description richness: word count normalized (target ~100 words)
        word_count = len(job.generated_description.split())
        description_richness = min(word_count / 100.0, 1.0)

        # Overall weighted score
        overall = (
            completeness * 0.35
            + image_quality_score * 0.35
            + description_richness * 0.30
        )

        # Generate recommendations
        recommendations: list[str] = []
        if completeness < 0.7:
            recommendations.append("Increase attribute completeness — some fields are missing")
        if image_quality_score < 0.7:
            recommendations.append("Improve product image quality for better AI extraction")
        if description_richness < 0.7:
            recommendations.append("Description is too brief — consider enriching product context")
        if self._enrichment_service.should_trigger_human_review(job.confidence_scores):
            recommendations.append("Low confidence detected — human review recommended")

        return QualityReport(
            product_id=job.product_id,
            tenant_id=tenant_id,
            completeness_score=round(completeness, 3),
            image_quality_score=round(image_quality_score, 3),
            description_richness_score=round(description_richness, 3),
            overall_score=round(overall, 3),
            recommendations=tuple(recommendations),
        )
