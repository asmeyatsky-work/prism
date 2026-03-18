"""
Intelligence Application Query — Get Enrichment Status

Architectural Intent:
- Read-side query returning the current state of an enrichment job
- Returns a DTO (never exposes domain entities to callers)
- Tenant-scoped: queries are always within a tenant boundary
"""

from __future__ import annotations

from prism.intelligence.application.dtos.enrichment_dto import EnrichmentJobDTO
from prism.intelligence.domain.entities.enrichment_job import EnrichmentJob
from prism.shared.application.dtos import QueryResult, TenantContext
from prism.shared.domain.ports import RepositoryPort
from prism.shared.domain.value_objects import TenantId


class GetEnrichmentStatusQuery:
    """
    Query to retrieve the current status of an enrichment job.

    Returns an EnrichmentJobDTO containing all current state including
    extracted attributes, generated description, confidence scores,
    and any error information.
    """

    def __init__(
        self,
        job_repository: RepositoryPort[EnrichmentJob],
    ) -> None:
        self._job_repo = job_repository

    async def execute(
        self,
        job_id: str,
        tenant_context: TenantContext,
    ) -> QueryResult[EnrichmentJobDTO]:
        """
        Retrieve the current status of an enrichment job.

        Args:
            job_id: The enrichment job identifier.
            tenant_context: Tenant scope for multi-tenancy.

        Returns:
            QueryResult wrapping an EnrichmentJobDTO, or a failure
            result if the job is not found.
        """
        tenant_id = TenantId(value=tenant_context.tenant_id)
        job = await self._job_repo.get_by_id(job_id, tenant_id)

        if job is None:
            return QueryResult.fail(
                f"Enrichment job '{job_id}' not found for tenant '{tenant_id.value}'"
            )

        dto = EnrichmentJobDTO.from_entity(job)
        return QueryResult.ok(dto)
