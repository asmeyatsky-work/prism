"""
Ingest Product Command and Use Case

Architectural Intent:
- Command represents the intent to ingest a new product into the catalogue
- Use case orchestrates: validate -> create aggregate -> persist -> publish events
- Depends on domain ports (repository, event bus) — never on infrastructure directly
- Returns CommandResult for consistent success/failure semantics

Design Notes:
- Duplicate SKU detection prevents silent overwrites
- Quality score is computed on ingest so dashboards reflect data health immediately
- Domain events are dispatched after successful persistence (not before)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from prism.catalogue.application.dtos.product_dto import ProductDTO
from prism.catalogue.domain.entities.product import Product
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.catalogue.domain.services.quality_service import QualityService
from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort
from prism.shared.domain.value_objects import Currency, ImageRef, Money, TenantId


class IngestProductCommand(BaseModel):
    """
    Command to ingest a new product into the catalogue.

    Carries all data needed to create a Product aggregate from a UCP feed
    or manual entry.
    """

    tenant_id: str
    sku: str
    name: str
    brand: str
    description: str = ""
    category: str = ""
    subcategory: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    image_uris: list[str] = Field(default_factory=list)
    price_amount: float | None = None
    price_currency: str = "USD"
    taxonomy_codes: list[str] = Field(default_factory=list)
    source: str = "manual"

    model_config = {"frozen": True}


class IngestProductUseCase:
    """
    Use case for ingesting a new product into the catalogue.

    Orchestrates the full ingest flow:
    1. Validate no duplicate SKU exists for the tenant
    2. Create the Product aggregate via its factory method
    3. Compute an initial quality score
    4. Persist the product
    5. Publish domain events (ProductIngestedEvent)

    Dependencies are injected as domain ports — this class never touches
    infrastructure directly.
    """

    def __init__(
        self,
        product_repository: ProductRepositoryPort,
        event_bus: EventBusPort,
        quality_service: QualityService | None = None,
    ) -> None:
        self._product_repo = product_repository
        self._event_bus = event_bus
        self._quality_service = quality_service or QualityService()

    async def execute(self, command: IngestProductCommand) -> CommandResult[ProductDTO]:
        """
        Execute the product ingestion workflow.

        Args:
            command: The ingest product command with all product data.

        Returns:
            CommandResult containing the ProductDTO on success, or an error
            on failure (e.g., duplicate SKU).
        """
        tenant_id = TenantId(value=command.tenant_id)

        # 1. Check for duplicate SKU
        existing = await self._product_repo.get_by_sku(command.sku, tenant_id)
        if existing is not None:
            return CommandResult.fail(
                f"Product with SKU '{command.sku}' already exists for tenant "
                f"'{command.tenant_id}'",
                code="DUPLICATE_SKU",
            )

        # 2. Build image references from URIs
        images = self._parse_image_uris(command.image_uris)

        # 3. Build price if provided
        price = None
        if command.price_amount is not None:
            try:
                currency = Currency(command.price_currency)
            except ValueError:
                return CommandResult.fail(
                    f"Unsupported currency: '{command.price_currency}'",
                    code="INVALID_CURRENCY",
                )
            price = Money(amount=command.price_amount, currency=currency)

        # 4. Create the Product aggregate (emits ProductIngestedEvent)
        product = Product.create(
            tenant_id=tenant_id,
            sku=command.sku,
            name=command.name,
            brand=command.brand,
            description=command.description,
            category=command.category,
            subcategory=command.subcategory,
            attributes=command.attributes if command.attributes else None,
            images=images,
            price=price,
            taxonomy_codes=tuple(command.taxonomy_codes),
            source=command.source,
        )

        # 5. Compute initial quality score
        score = self._quality_service.calculate_quality_score(product)
        product = product.update_quality_score(score)

        # 6. Persist
        await self._product_repo.save(product)

        # 7. Publish domain events
        if product.domain_events:
            await self._event_bus.publish(list(product.domain_events))

        # 8. Clear events and return DTO
        product = product.clear_events()
        dto = ProductDTO.from_domain(product)

        return CommandResult.ok(dto)

    @staticmethod
    def _parse_image_uris(uris: list[str]) -> tuple[ImageRef, ...]:
        """
        Parse GCS URIs into ImageRef value objects.

        Expected format: gs://bucket/path/to/image.jpg

        Args:
            uris: List of GCS URI strings.

        Returns:
            Tuple of ImageRef value objects.
        """
        images: list[ImageRef] = []
        for uri in uris:
            if uri.startswith("gs://"):
                # Strip gs:// prefix and split bucket/path
                without_prefix = uri[5:]
                parts = without_prefix.split("/", 1)
                if len(parts) == 2:
                    bucket, path = parts
                    content_type = "image/jpeg"
                    if path.endswith(".png"):
                        content_type = "image/png"
                    elif path.endswith(".webp"):
                        content_type = "image/webp"
                    images.append(
                        ImageRef(bucket=bucket, path=path, content_type=content_type)
                    )
        return tuple(images)
