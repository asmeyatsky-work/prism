"""
Intelligence Domain Ports — Quality Assessment Interfaces

Architectural Intent:
- Protocol-based ports for image quality assessment and quality report persistence
- ImageQualityPort abstracts technical image quality analysis
- QualityReportRepositoryPort follows the shared RepositoryPort pattern
  but is specialised for QualityReport (not an AggregateRoot)
- All operations are async and tenant-scoped
"""

from __future__ import annotations

from typing import Protocol

from prism.intelligence.domain.entities.quality_report import QualityReport
from prism.shared.domain.value_objects import ImageRef, TenantId


class ImageQualityPort(Protocol):
    """
    Port for assessing technical quality of product imagery.

    Implementations analyse resolution, lighting, background consistency,
    and other factors relevant to luxury retail product photography.
    """

    async def assess_quality(self, images: list[ImageRef]) -> float:
        """
        Assess the technical quality of product images.

        Args:
            images: Product image references to evaluate.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        ...


class QualityReportRepositoryPort(Protocol):
    """
    Repository port for persisting and retrieving QualityReport entities.

    Follows the shared repository pattern but is specialised for
    QualityReport, which is an Entity (not AggregateRoot).
    """

    async def save(self, report: QualityReport, tenant_id: TenantId) -> None:
        """
        Persist a quality report.

        Args:
            report: The quality report to store.
            tenant_id: Tenant scope for multi-tenancy.
        """
        ...

    async def get_by_product_id(
        self,
        product_id: str,
        tenant_id: TenantId,
    ) -> QualityReport | None:
        """
        Retrieve the latest quality report for a product.

        Args:
            product_id: Product to look up.
            tenant_id: Tenant scope for multi-tenancy.

        Returns:
            The most recent QualityReport, or None if not found.
        """
        ...

    async def get_by_id(
        self,
        id: str,
        tenant_id: TenantId,
    ) -> QualityReport | None:
        """
        Retrieve a specific quality report by its ID.

        Args:
            id: Report identifier.
            tenant_id: Tenant scope for multi-tenancy.

        Returns:
            The QualityReport, or None if not found.
        """
        ...
