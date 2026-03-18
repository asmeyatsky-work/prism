"""
List Products Query

Architectural Intent:
- Paginated, tenant-scoped product listing query
- Returns ProductSummaryDTO for efficient list/grid rendering
- Supports optional text search with fallback to full listing
- Uses PaginationParams from the shared kernel for consistent pagination
"""

from __future__ import annotations

from pydantic import BaseModel

from prism.catalogue.application.dtos.product_dto import ProductSummaryDTO
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.shared.application.dtos import PaginationParams, QueryResult
from prism.shared.domain.value_objects import TenantId


class ListProductsQuery(BaseModel):
    """
    Query to list products for a tenant with optional search and pagination.

    When search_query is provided, delegates to the repository's search method.
    Otherwise, returns all products for the tenant ordered by creation date.
    """

    tenant_id: str
    search_query: str | None = None
    pagination: PaginationParams = PaginationParams()

    model_config = {"frozen": True}


class ListProductsQueryHandler:
    """
    Handler for the ListProductsQuery.

    Retrieves a paginated list of products, optionally filtered by a
    search query. Returns lightweight ProductSummaryDTOs suitable for
    catalogue browsing views.
    """

    def __init__(self, product_repository: ProductRepositoryPort) -> None:
        self._product_repo = product_repository

    async def execute(
        self, query: ListProductsQuery
    ) -> QueryResult[list[ProductSummaryDTO]]:
        """
        Execute the product listing query.

        Args:
            query: The list products query with tenant, search, and pagination.

        Returns:
            QueryResult containing a list of ProductSummaryDTOs and total count.
        """
        tenant_id = TenantId(value=query.tenant_id)
        offset = query.pagination.offset
        limit = query.pagination.limit

        if query.search_query:
            products, total_count = await self._product_repo.search(
                tenant_id,
                query.search_query,
                offset=offset,
                limit=limit,
            )
        else:
            products, total_count = await self._product_repo.list_by_tenant(
                tenant_id,
                offset=offset,
                limit=limit,
            )

        summaries = [ProductSummaryDTO.from_domain(p) for p in products]
        return QueryResult.ok(summaries, total_count=total_count)
