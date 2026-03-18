"""
Get Product Query

Architectural Intent:
- Single-product retrieval query returning a full ProductDTO
- Supports lookup by ID or by SKU within a tenant
- Returns QueryResult for consistent success/empty/failure semantics
- Read-only — no side effects or domain events
"""

from __future__ import annotations

from pydantic import BaseModel

from prism.catalogue.application.dtos.product_dto import ProductDTO
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.shared.application.dtos import QueryResult
from prism.shared.domain.value_objects import TenantId


class GetProductQuery(BaseModel):
    """
    Query to retrieve a single product by ID or SKU.

    Exactly one of product_id or sku must be provided.
    """

    tenant_id: str
    product_id: str | None = None
    sku: str | None = None

    model_config = {"frozen": True}


class GetProductQueryHandler:
    """
    Handler for the GetProductQuery.

    Fetches a single product from the repository and maps it to a ProductDTO.
    Supports lookup by either domain ID or SKU.
    """

    def __init__(self, product_repository: ProductRepositoryPort) -> None:
        self._product_repo = product_repository

    async def execute(self, query: GetProductQuery) -> QueryResult[ProductDTO]:
        """
        Execute the product retrieval query.

        Args:
            query: The get product query with tenant and identifier.

        Returns:
            QueryResult containing the ProductDTO if found, or empty/error.
        """
        if not query.product_id and not query.sku:
            return QueryResult.fail(
                "Either product_id or sku must be provided"
            )

        tenant_id = TenantId(value=query.tenant_id)

        if query.product_id:
            product = await self._product_repo.get_by_id(
                query.product_id, tenant_id
            )
        else:
            product = await self._product_repo.get_by_sku(
                query.sku,  # type: ignore[arg-type]
                tenant_id,
            )

        if product is None:
            return QueryResult.empty()

        dto = ProductDTO.from_domain(product)
        return QueryResult.ok(dto, total_count=1)
