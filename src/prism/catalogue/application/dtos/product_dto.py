"""
Catalogue DTOs — Product Data Transfer Objects

Architectural Intent:
- Pydantic models for API boundaries between application and presentation layers
- ProductDTO is the full representation; ProductSummaryDTO is the list/card view
- DTOs decouple the domain model from external consumers (MCP server, REST API)
- Immutable (frozen=True) to prevent accidental mutation at the boundary

Design Notes:
- Price is serialised as amount + currency string (not the Money value object)
- Images are serialised as GCS URIs for direct consumption by frontends
- Enrichment status is a plain string to avoid leaking domain enums to clients
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from prism.catalogue.domain.entities.product import Product


class ProductDTO(BaseModel):
    """
    Full product data transfer object for detailed views and API responses.

    Contains all product information including attributes, images, taxonomy,
    and enrichment metadata.
    """

    id: str
    tenant_id: str
    sku: str
    name: str
    brand: str
    description: str
    category: str
    subcategory: str
    attributes: dict[str, Any]
    image_uris: tuple[str, ...]
    price_amount: float | None = None
    price_currency: str | None = None
    taxonomy_codes: tuple[str, ...]
    enrichment_status: str
    quality_score: float
    embedding_vector_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"frozen": True}

    @staticmethod
    def from_domain(product: Product) -> ProductDTO:
        """
        Map a Product aggregate to a ProductDTO.

        Args:
            product: The domain Product aggregate.

        Returns:
            ProductDTO with all fields mapped from the domain entity.
        """
        return ProductDTO(
            id=product.id,
            tenant_id=product.tenant_id.value,
            sku=product.sku,
            name=product.name,
            brand=product.brand,
            description=product.description,
            category=product.category,
            subcategory=product.subcategory,
            attributes=product.attributes,
            image_uris=tuple(img.gcs_uri for img in product.images),
            price_amount=product.price.amount if product.price else None,
            price_currency=product.price.currency.value if product.price else None,
            taxonomy_codes=product.taxonomy_codes,
            enrichment_status=product.enrichment_status.value,
            quality_score=product.quality_score,
            embedding_vector_id=product.embedding_vector_id,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )


class ProductSummaryDTO(BaseModel):
    """
    Lightweight product summary for list views and catalogue cards.

    Includes only the fields needed for rendering a product card in a list
    or grid view — minimises data transfer for paginated responses.
    """

    id: str
    tenant_id: str
    sku: str
    name: str
    brand: str
    category: str
    primary_image_uri: str | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    enrichment_status: str
    quality_score: float

    model_config = {"frozen": True}

    @staticmethod
    def from_domain(product: Product) -> ProductSummaryDTO:
        """
        Map a Product aggregate to a ProductSummaryDTO.

        Args:
            product: The domain Product aggregate.

        Returns:
            ProductSummaryDTO with summary fields mapped.
        """
        primary_image = product.images[0].gcs_uri if product.images else None

        return ProductSummaryDTO(
            id=product.id,
            tenant_id=product.tenant_id.value,
            sku=product.sku,
            name=product.name,
            brand=product.brand,
            category=product.category,
            primary_image_uri=primary_image,
            price_amount=product.price.amount if product.price else None,
            price_currency=product.price.currency.value if product.price else None,
            enrichment_status=product.enrichment_status.value,
            quality_score=product.quality_score,
        )
