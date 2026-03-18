"""
Update Product Command and Use Case

Architectural Intent:
- Command represents the intent to update an existing product's mutable fields
- Use case orchestrates: fetch -> validate -> apply changes -> persist -> publish events
- Supports partial updates — only provided fields are modified
- Quality score is recomputed after every update

Design Notes:
- Cannot change tenant_id or SKU (identity fields)
- Enrichment status transitions are handled by dedicated domain methods (enrich, mark_as_reviewed)
- This use case handles general field updates (name, description, category, etc.)
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from pydantic import BaseModel, Field

from prism.catalogue.application.dtos.product_dto import ProductDTO
from prism.catalogue.domain.ports.repository_ports import ProductRepositoryPort
from prism.catalogue.domain.services.quality_service import QualityService
from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort
from prism.shared.domain.value_objects import Currency, Money, TenantId


class UpdateProductCommand(BaseModel):
    """
    Command to update an existing product in the catalogue.

    All fields except tenant_id and product_id are optional — only provided
    fields will be applied to the product.
    """

    tenant_id: str
    product_id: str
    name: str | None = None
    description: str | None = None
    category: str | None = None
    subcategory: str | None = None
    attributes: dict[str, Any] | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    taxonomy_codes: list[str] | None = None

    model_config = {"frozen": True}


class UpdateProductUseCase:
    """
    Use case for updating an existing product in the catalogue.

    Orchestrates the update flow:
    1. Fetch the existing product
    2. Apply provided changes via dataclass replace
    3. Recompute quality score
    4. Persist the updated product
    5. Publish any accumulated domain events

    Dependencies are injected as domain ports.
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

    async def execute(self, command: UpdateProductCommand) -> CommandResult[ProductDTO]:
        """
        Execute the product update workflow.

        Args:
            command: The update product command with fields to change.

        Returns:
            CommandResult containing the updated ProductDTO on success,
            or an error on failure (e.g., product not found).
        """
        tenant_id = TenantId(value=command.tenant_id)

        # 1. Fetch existing product
        product = await self._product_repo.get_by_id(command.product_id, tenant_id)
        if product is None:
            return CommandResult.fail(
                f"Product '{command.product_id}' not found for tenant "
                f"'{command.tenant_id}'",
                code="PRODUCT_NOT_FOUND",
            )

        # 2. Build replacement kwargs from provided fields
        updates: dict[str, Any] = {}

        if command.name is not None:
            updates["name"] = command.name
        if command.description is not None:
            updates["description"] = command.description
        if command.category is not None:
            updates["category"] = command.category
        if command.subcategory is not None:
            updates["subcategory"] = command.subcategory
        if command.attributes is not None:
            # Merge with existing attributes
            updates["attributes"] = {**product.attributes, **command.attributes}
        if command.taxonomy_codes is not None:
            updates["taxonomy_codes"] = tuple(command.taxonomy_codes)
        if command.price_amount is not None:
            currency_str = command.price_currency or (
                product.price.currency.value if product.price else "USD"
            )
            try:
                currency = Currency(currency_str)
            except ValueError:
                return CommandResult.fail(
                    f"Unsupported currency: '{currency_str}'",
                    code="INVALID_CURRENCY",
                )
            updates["price"] = Money(amount=command.price_amount, currency=currency)

        if not updates:
            # No changes requested — return current state
            dto = ProductDTO.from_domain(product)
            return CommandResult.ok(dto)

        # 3. Apply changes
        updates.update(product._touch())
        product = replace(product, **updates)

        # 4. Recompute quality score
        score = self._quality_service.calculate_quality_score(product)
        product = product.update_quality_score(score)

        # 5. Persist
        await self._product_repo.save(product)

        # 6. Publish domain events
        if product.domain_events:
            await self._event_bus.publish(list(product.domain_events))

        product = product.clear_events()
        dto = ProductDTO.from_domain(product)

        return CommandResult.ok(dto)
