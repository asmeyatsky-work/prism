"""
Catalogue Repository Ports

Architectural Intent:
- Protocol-based interfaces defining persistence contracts for the Catalogue context
- Infrastructure adapters (BigQuery, Firestore, etc.) implement these protocols
- All operations are tenant-scoped — multi-tenancy enforced at the port level
- Async by default for compatibility with Cloud-native infrastructure

Design Notes:
- ProductRepositoryPort includes search() for full-text/vector search delegation
- BrandRepositoryPort is simpler — brands are a supporting entity, not an aggregate
- These protocols extend beyond the generic RepositoryPort to include
  domain-specific query methods (get_by_sku, search)
"""

from __future__ import annotations

from typing import Protocol

from prism.catalogue.domain.entities.brand import Brand
from prism.catalogue.domain.entities.product import Product
from prism.shared.domain.value_objects import TenantId


class ProductRepositoryPort(Protocol):
    """
    Repository port for Product aggregate persistence and retrieval.

    Implementations must ensure tenant isolation — a product from one tenant
    must never be accessible via another tenant's queries.
    """

    async def get_by_id(self, product_id: str, tenant_id: TenantId) -> Product | None:
        """
        Retrieve a product by its unique identifier.

        Args:
            product_id: The product's domain ID.
            tenant_id: The owning tenant.

        Returns:
            The Product if found, None otherwise.
        """
        ...

    async def get_by_sku(self, sku: str, tenant_id: TenantId) -> Product | None:
        """
        Retrieve a product by its SKU within a tenant.

        Args:
            sku: Stock Keeping Unit.
            tenant_id: The owning tenant.

        Returns:
            The Product if found, None otherwise.
        """
        ...

    async def save(self, product: Product) -> None:
        """
        Persist a product (insert or update).

        Implementations should use upsert semantics keyed on (tenant_id, id).

        Args:
            product: The Product aggregate to persist.
        """
        ...

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        """
        List products for a tenant with pagination.

        Args:
            tenant_id: The owning tenant.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (product list, total count).
        """
        ...

    async def search(
        self,
        tenant_id: TenantId,
        query: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        """
        Search products by text query within a tenant.

        Implementations may delegate to full-text search (BigQuery Search Index)
        or vector search (Vertex AI Matching Engine) depending on configuration.

        Args:
            tenant_id: The owning tenant.
            query: Search query string.
            offset: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (matching products, total count).
        """
        ...


class BrandRepositoryPort(Protocol):
    """
    Repository port for Brand entity persistence and retrieval.

    Brands are a supporting entity — they hold tenant-level configuration
    rather than transactional data.
    """

    async def get_by_id(self, brand_id: str, tenant_id: TenantId) -> Brand | None:
        """
        Retrieve a brand by its unique identifier.

        Args:
            brand_id: The brand's domain ID.
            tenant_id: The owning tenant.

        Returns:
            The Brand if found, None otherwise.
        """
        ...

    async def save(self, brand: Brand) -> None:
        """
        Persist a brand (insert or update).

        Args:
            brand: The Brand entity to persist.
        """
        ...

    async def list_all(self, tenant_id: TenantId) -> list[Brand]:
        """
        List all brands for a tenant.

        In most deployments there is a 1:1 mapping between tenant and brand,
        but the platform supports multi-brand tenants (e.g., conglomerate groups).

        Args:
            tenant_id: The owning tenant.

        Returns:
            List of all brands for the tenant.
        """
        ...
