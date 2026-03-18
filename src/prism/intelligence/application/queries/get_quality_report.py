"""
Intelligence Application Query — Get Quality Report

Architectural Intent:
- Read-side query returning the latest quality report for a product
- Returns a DTO (never exposes domain entities to callers)
- Tenant-scoped: queries are always within a tenant boundary
"""

from __future__ import annotations

from prism.intelligence.application.dtos.enrichment_dto import QualityReportDTO
from prism.intelligence.domain.ports.quality_ports import QualityReportRepositoryPort
from prism.shared.application.dtos import QueryResult, TenantContext
from prism.shared.domain.value_objects import TenantId


class GetQualityReportQuery:
    """
    Query to retrieve the latest quality report for a product.

    Returns a QualityReportDTO with scores, acceptability status,
    and actionable recommendations.
    """

    def __init__(
        self,
        quality_report_repository: QualityReportRepositoryPort,
    ) -> None:
        self._quality_repo = quality_report_repository

    async def execute(
        self,
        product_id: str,
        tenant_context: TenantContext,
    ) -> QueryResult[QualityReportDTO]:
        """
        Retrieve the latest quality report for a product.

        Args:
            product_id: The product identifier.
            tenant_context: Tenant scope for multi-tenancy.

        Returns:
            QueryResult wrapping a QualityReportDTO, or a failure
            result if no report exists for the product.
        """
        tenant_id = TenantId(value=tenant_context.tenant_id)
        report = await self._quality_repo.get_by_product_id(product_id, tenant_id)

        if report is None:
            return QueryResult.fail(
                f"Quality report not found for product '{product_id}' "
                f"in tenant '{tenant_id.value}'"
            )

        dto = QualityReportDTO.from_entity(report)
        return QueryResult.ok(dto)
