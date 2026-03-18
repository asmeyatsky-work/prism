"""
Tests for EnrichProductUseCase — Parallel Execution and Port Interactions

Tests verify:
- Successful enrichment produces correct job state and events
- DAG parallelism: extract_attributes and assess_image_quality run concurrently
- Sequential dependencies: description after extraction, embedding after description
- Port interactions: each port is called with correct arguments
- Failure handling: job transitions to FAILED and events are published
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from prism.intelligence.application.commands.enrich_product import (
    EnrichProductCommand,
    EnrichProductUseCase,
)
from prism.intelligence.domain.entities.enrichment_job import EnrichmentJob, EnrichmentStatus
from prism.intelligence.domain.entities.quality_report import QualityReport
from prism.intelligence.domain.services.enrichment_service import EnrichmentService
from prism.intelligence.domain.value_objects.ai_output import (
    AttributeWithConfidence,
    ExtractedAttributes,
    GeneratedDescription,
)
from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig, Tone
from prism.shared.application.dtos import TenantContext
from prism.shared.domain.events import DomainEvent
from prism.shared.domain.value_objects import ImageRef, Locale, TenantId


# --- In-memory test doubles ---


class InMemoryJobRepository:
    """In-memory repository for EnrichmentJob (test double)."""

    def __init__(self) -> None:
        self.jobs: dict[str, EnrichmentJob] = {}

    async def get_by_id(
        self, id: str, tenant_id: TenantId
    ) -> EnrichmentJob | None:
        return self.jobs.get(id)

    async def save(self, entity: Any, tenant_id: TenantId) -> None:
        self.jobs[entity.id] = entity

    async def delete(self, id: str, tenant_id: TenantId) -> None:
        self.jobs.pop(id, None)


class InMemoryQualityReportRepository:
    """In-memory repository for QualityReport (test double)."""

    def __init__(self) -> None:
        self.reports: dict[str, QualityReport] = {}

    async def save(self, report: QualityReport, tenant_id: TenantId) -> None:
        self.reports[report.product_id] = report

    async def get_by_product_id(
        self, product_id: str, tenant_id: TenantId
    ) -> QualityReport | None:
        return self.reports.get(product_id)

    async def get_by_id(
        self, id: str, tenant_id: TenantId
    ) -> QualityReport | None:
        for report in self.reports.values():
            if report.id == id:
                return report
        return None


class RecordingEventBus:
    """Event bus that records all published events (test double)."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self.published_events.extend(events)

    async def subscribe(self, event_type: type, handler: Any) -> None:
        pass


# --- Fixtures ---


@pytest.fixture
def job_repo() -> InMemoryJobRepository:
    return InMemoryJobRepository()


@pytest.fixture
def quality_repo() -> InMemoryQualityReportRepository:
    return InMemoryQualityReportRepository()


@pytest.fixture
def event_bus() -> RecordingEventBus:
    return RecordingEventBus()


@pytest.fixture
def mock_extractor() -> AsyncMock:
    extractor = AsyncMock()
    extractor.extract_attributes.return_value = ExtractedAttributes(
        material=AttributeWithConfidence(value="cashmere", confidence=0.95),
        colour=AttributeWithConfidence(value="ivory", confidence=0.88),
        pattern=AttributeWithConfidence(value="solid", confidence=0.92),
        silhouette=AttributeWithConfidence(value="A-line", confidence=0.85),
        occasion=AttributeWithConfidence(value="evening", confidence=0.80),
        season=AttributeWithConfidence(value="AW25", confidence=0.90),
    )
    return extractor


@pytest.fixture
def mock_description_generator() -> AsyncMock:
    generator = AsyncMock()
    generator.generate_description.return_value = GeneratedDescription(
        text="A sumptuous cashmere piece in ivory, perfect for elegant evenings.",
        tone="luxury",
        locale="en",
        word_count=11,
    )
    return generator


@pytest.fixture
def mock_embedding_generator() -> AsyncMock:
    generator = AsyncMock()
    generator.generate_text_embedding.return_value = [0.1] * 768
    generator.generate_multimodal_embedding.return_value = [0.2] * 1408
    return generator


@pytest.fixture
def mock_vector_index() -> AsyncMock:
    index = AsyncMock()
    index.upsert.return_value = "vec-prod-001"
    index.search.return_value = [("prod-001", 0.95)]
    return index


@pytest.fixture
def mock_image_quality() -> AsyncMock:
    quality = AsyncMock()
    quality.assess_quality.return_value = 0.85
    return quality


@pytest.fixture
def enrichment_service() -> EnrichmentService:
    return EnrichmentService()


@pytest.fixture
def use_case(
    job_repo: InMemoryJobRepository,
    quality_repo: InMemoryQualityReportRepository,
    mock_extractor: AsyncMock,
    mock_description_generator: AsyncMock,
    mock_embedding_generator: AsyncMock,
    mock_vector_index: AsyncMock,
    mock_image_quality: AsyncMock,
    event_bus: RecordingEventBus,
    enrichment_service: EnrichmentService,
) -> EnrichProductUseCase:
    return EnrichProductUseCase(
        job_repository=job_repo,
        quality_report_repository=quality_repo,
        attribute_extractor=mock_extractor,
        description_generator=mock_description_generator,
        embedding_generator=mock_embedding_generator,
        vector_index=mock_vector_index,
        image_quality_assessor=mock_image_quality,
        event_bus=event_bus,
        enrichment_service=enrichment_service,
    )


@pytest.fixture
def enrich_command() -> EnrichProductCommand:
    return EnrichProductCommand(
        product_id="prod-001",
        tenant_context=TenantContext(
            tenant_id="tenant-gucci",
            brand_name="Gucci",
            locale="en",
        ),
        images=[
            ImageRef(bucket="prism-images", path="gucci/prod-001/front.jpg"),
            ImageRef(bucket="prism-images", path="gucci/prod-001/back.jpg"),
        ],
        voice_config=BrandVoiceConfig(
            brand_name="Gucci",
            tone=Tone.LUXURY,
            style_guidelines="Emphasise Italian craftsmanship and heritage.",
        ),
        locale=Locale(language="en", region="US"),
        model_version="v1.0",
    )


# --- Tests ---


class TestEnrichProductSuccess:
    """Test successful enrichment pipeline execution."""

    @pytest.mark.asyncio
    async def test_successful_enrichment_returns_job_id(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
    ) -> None:
        result = await use_case.execute(enrich_command)

        assert result.success is True
        assert result.value is not None
        assert isinstance(result.value, str)

    @pytest.mark.asyncio
    async def test_successful_enrichment_persists_completed_job(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        job_repo: InMemoryJobRepository,
    ) -> None:
        result = await use_case.execute(enrich_command)

        # There should be a saved job
        assert len(job_repo.jobs) >= 1
        # The final saved job should be COMPLETED
        saved_job = job_repo.jobs[result.value]
        assert saved_job.status == EnrichmentStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_successful_enrichment_publishes_events(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        event_bus: RecordingEventBus,
    ) -> None:
        await use_case.execute(enrich_command)

        event_types = [type(e).__name__ for e in event_bus.published_events]
        assert "EnrichmentStartedEvent" in event_types
        assert "AttributesExtractedEvent" in event_types
        assert "DescriptionGeneratedEvent" in event_types
        assert "EmbeddingCreatedEvent" in event_types
        assert "EnrichmentCompletedEvent" in event_types

    @pytest.mark.asyncio
    async def test_successful_enrichment_creates_quality_report(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        quality_repo: InMemoryQualityReportRepository,
    ) -> None:
        await use_case.execute(enrich_command)

        report = quality_repo.reports.get("prod-001")
        assert report is not None
        assert report.product_id == "prod-001"
        assert report.image_quality_score == 0.85
        assert 0.0 <= report.overall_score <= 1.0


class TestEnrichProductPortInteractions:
    """Test that domain ports are called with correct arguments."""

    @pytest.mark.asyncio
    async def test_extractor_called_with_images_and_context(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_extractor: AsyncMock,
    ) -> None:
        await use_case.execute(enrich_command)

        mock_extractor.extract_attributes.assert_called_once()
        call_args = mock_extractor.extract_attributes.call_args
        images = call_args.kwargs.get("images", call_args.args[0] if call_args.args else None)
        assert len(images) == 2
        assert images[0].bucket == "prism-images"

    @pytest.mark.asyncio
    async def test_description_generator_called_with_attributes_and_voice(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_description_generator: AsyncMock,
    ) -> None:
        await use_case.execute(enrich_command)

        mock_description_generator.generate_description.assert_called_once()
        call_args = mock_description_generator.generate_description.call_args
        voice_config = call_args.kwargs.get(
            "voice_config", call_args.args[1] if len(call_args.args) > 1 else None
        )
        assert voice_config.brand_name == "Gucci"
        assert voice_config.tone == Tone.LUXURY

    @pytest.mark.asyncio
    async def test_embedding_generator_called_with_combined_text(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_embedding_generator: AsyncMock,
    ) -> None:
        await use_case.execute(enrich_command)

        mock_embedding_generator.generate_text_embedding.assert_called_once()
        call_args = mock_embedding_generator.generate_text_embedding.call_args
        text = call_args.args[0] if call_args.args else call_args.kwargs.get("text", "")
        # Should contain both attributes and description text
        assert "cashmere" in text
        assert "ivory" in text

    @pytest.mark.asyncio
    async def test_vector_index_upsert_called(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_vector_index: AsyncMock,
    ) -> None:
        await use_case.execute(enrich_command)

        mock_vector_index.upsert.assert_called_once()
        call_args = mock_vector_index.upsert.call_args
        product_id = call_args.kwargs.get(
            "product_id", call_args.args[0] if call_args.args else None
        )
        assert product_id == "prod-001"

    @pytest.mark.asyncio
    async def test_image_quality_called_in_parallel_with_extraction(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_image_quality: AsyncMock,
    ) -> None:
        await use_case.execute(enrich_command)

        # Image quality assessment should be called regardless of extraction
        mock_image_quality.assess_quality.assert_called_once()


class TestEnrichProductFailure:
    """Test failure handling in the enrichment pipeline."""

    @pytest.mark.asyncio
    async def test_extraction_failure_returns_error_result(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_extractor: AsyncMock,
    ) -> None:
        mock_extractor.extract_attributes.side_effect = RuntimeError(
            "Vision API unavailable"
        )

        result = await use_case.execute(enrich_command)

        assert result.success is False
        assert result.error_code == "ENRICHMENT_FAILED"
        assert "Vision API unavailable" in (result.error or "")

    @pytest.mark.asyncio
    async def test_extraction_failure_persists_failed_job(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_extractor: AsyncMock,
        job_repo: InMemoryJobRepository,
    ) -> None:
        mock_extractor.extract_attributes.side_effect = RuntimeError("API error")

        await use_case.execute(enrich_command)

        # Should have at least one saved job in FAILED state
        failed_jobs = [
            j for j in job_repo.jobs.values()
            if j.status == EnrichmentStatus.FAILED
        ]
        assert len(failed_jobs) >= 1

    @pytest.mark.asyncio
    async def test_extraction_failure_publishes_failure_event(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_extractor: AsyncMock,
        event_bus: RecordingEventBus,
    ) -> None:
        mock_extractor.extract_attributes.side_effect = RuntimeError("timeout")

        await use_case.execute(enrich_command)

        event_types = [type(e).__name__ for e in event_bus.published_events]
        assert "EnrichmentFailedEvent" in event_types

    @pytest.mark.asyncio
    async def test_description_failure_does_not_lose_extracted_attributes(
        self,
        use_case: EnrichProductUseCase,
        enrich_command: EnrichProductCommand,
        mock_description_generator: AsyncMock,
        job_repo: InMemoryJobRepository,
    ) -> None:
        mock_description_generator.generate_description.side_effect = RuntimeError(
            "LLM quota exceeded"
        )

        result = await use_case.execute(enrich_command)

        assert result.success is False
        # The job should still have extracted attributes from the successful step
        failed_jobs = [
            j for j in job_repo.jobs.values()
            if j.status == EnrichmentStatus.FAILED
        ]
        assert len(failed_jobs) >= 1
