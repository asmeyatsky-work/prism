"""
Product Aggregate Root

Architectural Intent:
- The canonical Product aggregate is the core of the Catalogue bounded context
- Immutable (frozen dataclass) — all mutations return a new instance plus domain events
- Enrichment lifecycle: RAW -> ENRICHING -> ENRICHED -> REVIEWED
- Tenant-scoped via TenantId for multi-brand platform isolation
- Domain events are appended on each state transition for downstream consumption

Design Notes:
- attributes dict holds arbitrary key-value product attributes for flexibility
- images are a tuple of ImageRef (immutable sequence) for Cloud Storage references
- taxonomy_codes are string-based for serialisation simplicity; see TaxonomyCode VO for typed access
- embedding_vector_id links to the vector store for semantic search
- quality_score is a domain-computed metric (0.0 to 1.0) for catalogue health dashboards
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any

from prism.catalogue.domain.events.catalogue_events import (
    ProductEnrichedEvent,
    ProductIngestedEvent,
    ProductReviewedEvent,
)
from prism.shared.domain.entities import AggregateRoot
from prism.shared.domain.value_objects import ImageRef, Money, TenantId


class EnrichmentStatus(str, Enum):
    """
    Product enrichment lifecycle states.

    RAW: Freshly ingested, no AI enrichment applied.
    ENRICHING: AI enrichment pipeline is currently processing.
    ENRICHED: AI enrichment complete, awaiting human review.
    REVIEWED: Human-reviewed and approved for production use.
    """

    RAW = "RAW"
    ENRICHING = "ENRICHING"
    ENRICHED = "ENRICHED"
    REVIEWED = "REVIEWED"


@dataclass(frozen=True)
class Product(AggregateRoot):
    """
    Product aggregate root — the central entity in the Catalogue context.

    Represents a single SKU in a luxury retail brand's catalogue. Progresses
    through an enrichment lifecycle from raw ingestion to human-reviewed,
    production-ready state.

    All mutations return a new Product instance (immutability) and append
    domain events for cross-context communication.

    Attributes:
        tenant_id: Owning brand/tenant for multi-tenant isolation.
        sku: Stock Keeping Unit — unique within a tenant.
        name: Product display name.
        brand: Brand name (denormalised for query convenience).
        description: Full editorial product description.
        category: Top-level product category.
        subcategory: Second-level product category.
        attributes: Arbitrary key-value product attributes.
        images: Ordered tuple of image references in Cloud Storage.
        price: Product price with currency.
        taxonomy_codes: PRISM taxonomy classification codes.
        enrichment_status: Current position in the enrichment lifecycle.
        quality_score: Computed data quality metric (0.0 to 1.0).
        embedding_vector_id: Reference to the product's vector in the embedding store.
    """

    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    sku: str = ""
    name: str = ""
    brand: str = ""
    description: str = ""
    category: str = ""
    subcategory: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    images: tuple[ImageRef, ...] = ()
    price: Money | None = None
    taxonomy_codes: tuple[str, ...] = ()
    enrichment_status: EnrichmentStatus = EnrichmentStatus.RAW
    quality_score: float = 0.0
    embedding_vector_id: str | None = None

    def __post_init__(self) -> None:
        if self.quality_score < 0.0 or self.quality_score > 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {self.quality_score}"
            )

    def enrich(self, enriched_attributes: dict[str, Any]) -> Product:
        """
        Apply AI-enriched attributes and transition to ENRICHED status.

        Merges enriched_attributes into existing attributes, updates the
        enrichment status, and appends a ProductEnrichedEvent.

        Args:
            enriched_attributes: Dictionary of AI-extracted product attributes.

        Returns:
            New Product instance with enriched data and appended domain event.

        Raises:
            ValueError: If the product is already REVIEWED (cannot re-enrich).
        """
        if self.enrichment_status == EnrichmentStatus.REVIEWED:
            raise ValueError(
                "Cannot enrich a product that has already been reviewed. "
                "Create a new version instead."
            )

        merged_attributes = {**self.attributes, **enriched_attributes}
        previous_score = self.quality_score

        enriched = replace(
            self,
            attributes=merged_attributes,
            enrichment_status=EnrichmentStatus.ENRICHED,
            **self._touch(),
        )

        event = ProductEnrichedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            sku=self.sku,
            enriched_fields=tuple(enriched_attributes.keys()),
            quality_score_before=previous_score,
            quality_score_after=enriched.quality_score,
        )
        return replace(
            enriched,
            domain_events=self.domain_events + (event,),
        )

    def update_quality_score(self, score: float) -> Product:
        """
        Update the product's data quality score.

        Args:
            score: New quality score between 0.0 and 1.0.

        Returns:
            New Product instance with updated quality score.

        Raises:
            ValueError: If score is outside the valid range.
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Quality score must be between 0.0 and 1.0, got {score}")

        return replace(
            self,
            quality_score=score,
            **self._touch(),
        )

    def add_image(self, image: ImageRef) -> Product:
        """
        Append an image reference to the product's image list.

        Args:
            image: ImageRef pointing to the asset in Cloud Storage.

        Returns:
            New Product instance with the image appended.
        """
        return replace(
            self,
            images=self.images + (image,),
            **self._touch(),
        )

    def update_taxonomy(self, taxonomy_codes: tuple[str, ...]) -> Product:
        """
        Replace the product's taxonomy classification codes.

        Args:
            taxonomy_codes: New tuple of PRISM taxonomy codes.

        Returns:
            New Product instance with updated taxonomy codes.
        """
        return replace(
            self,
            taxonomy_codes=taxonomy_codes,
            **self._touch(),
        )

    def mark_as_reviewed(self, reviewer_id: str) -> Product:
        """
        Transition the product to REVIEWED status after human approval.

        Only products in ENRICHED status can be reviewed. This marks the
        product as production-ready for storefront and discovery indexing.

        Args:
            reviewer_id: Identifier of the human reviewer approving the product.

        Returns:
            New Product instance in REVIEWED status with appended event.

        Raises:
            ValueError: If the product is not in ENRICHED status.
        """
        if self.enrichment_status != EnrichmentStatus.ENRICHED:
            raise ValueError(
                f"Only ENRICHED products can be reviewed. "
                f"Current status: {self.enrichment_status.value}"
            )

        event = ProductReviewedEvent(
            aggregate_id=self.id,
            tenant_id=self.tenant_id.value,
            sku=self.sku,
            reviewer_id=reviewer_id,
        )

        return replace(
            self,
            enrichment_status=EnrichmentStatus.REVIEWED,
            domain_events=self.domain_events + (event,),
            **self._touch(),
        )

    @staticmethod
    def create(
        *,
        tenant_id: TenantId,
        sku: str,
        name: str,
        brand: str,
        description: str = "",
        category: str = "",
        subcategory: str = "",
        attributes: dict[str, Any] | None = None,
        images: tuple[ImageRef, ...] = (),
        price: Money | None = None,
        taxonomy_codes: tuple[str, ...] = (),
        source: str = "manual",
    ) -> Product:
        """
        Factory method for creating a new Product with a ProductIngestedEvent.

        This is the preferred way to instantiate products — it ensures the
        ingestion event is always emitted.

        Args:
            tenant_id: Owning tenant.
            sku: Stock Keeping Unit.
            name: Product display name.
            brand: Brand name.
            description: Product description.
            category: Top-level category.
            subcategory: Second-level category.
            attributes: Initial product attributes.
            images: Initial image references.
            price: Product price.
            taxonomy_codes: Initial taxonomy codes.
            source: Ingestion source identifier.

        Returns:
            New Product instance with ProductIngestedEvent appended.
        """
        product = Product(
            tenant_id=tenant_id,
            sku=sku,
            name=name,
            brand=brand,
            description=description,
            category=category,
            subcategory=subcategory,
            attributes=attributes or {},
            images=images,
            price=price,
            taxonomy_codes=taxonomy_codes,
            enrichment_status=EnrichmentStatus.RAW,
            quality_score=0.0,
        )

        event = ProductIngestedEvent(
            aggregate_id=product.id,
            tenant_id=tenant_id.value,
            sku=sku,
            brand=brand,
            source=source,
        )

        return replace(
            product,
            domain_events=(event,),
        )
