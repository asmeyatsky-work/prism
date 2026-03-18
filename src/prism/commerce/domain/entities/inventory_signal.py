"""
Commerce Domain Entity — InventorySignal

Architectural Intent:
- Represents a point-in-time inventory availability signal for a product at a location
- Immutable snapshot — new signals replace old ones rather than mutating
- Fulfilment options are modelled as an immutable tuple of enum values
- Tenant-scoped for multi-brand isolation

Data Flow:
  UCP inventory event -> InventorySignal -> Discovery context (availability filters)
                                         -> Google Shopping feed (in_stock attribute)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import TenantId


class FulfilmentOption(str, Enum):
    """Available fulfilment methods for a product at a location."""

    SHIP = "SHIP"
    STORE_PICKUP = "STORE_PICKUP"
    SAME_DAY = "SAME_DAY"


@dataclass(frozen=True)
class InventorySignal(Entity):
    """
    Point-in-time inventory availability signal for a product at a specific location.

    Inventory signals are immutable snapshots. When availability changes, a new
    signal is created rather than mutating the existing one. This supports
    event-sourced inventory tracking and audit trails.

    Attributes:
        product_id: The product this signal refers to.
        tenant_id: Multi-tenant scope.
        available_quantity: Number of units available at this location.
        location: Physical or logical location identifier (warehouse, store, etc.).
        fulfilment_options: Tuple of available fulfilment methods.
        last_updated: Timestamp of the source system's last inventory update.
    """

    product_id: str = ""
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    available_quantity: int = 0
    location: str = ""
    fulfilment_options: tuple[FulfilmentOption, ...] = (FulfilmentOption.SHIP,)
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.product_id:
            raise ValueError("InventorySignal.product_id cannot be empty")
        if self.available_quantity < 0:
            raise ValueError(
                f"available_quantity must be non-negative, got {self.available_quantity}"
            )

    @property
    def is_in_stock(self) -> bool:
        """Whether any units are available."""
        return self.available_quantity > 0

    @property
    def supports_same_day(self) -> bool:
        """Whether same-day delivery is available at this location."""
        return FulfilmentOption.SAME_DAY in self.fulfilment_options

    @property
    def supports_store_pickup(self) -> bool:
        """Whether in-store pickup is available at this location."""
        return FulfilmentOption.STORE_PICKUP in self.fulfilment_options
