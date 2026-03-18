"""
Commerce Application Query — Get Inventory

Architectural Intent:
- Read-side query for retrieving inventory availability for a product
- Returns InventoryDTO for serialisation at the presentation boundary
- Delegates to InventoryPort for data access
- Returns QueryResult for consistent success/failure semantics
"""

from __future__ import annotations

from prism.commerce.application.dtos.commerce_dto import InventoryDTO
from prism.commerce.domain.ports.commerce_ports import InventoryPort
from prism.shared.application.dtos import QueryResult
from prism.shared.domain.value_objects import TenantId


class GetInventoryQuery:
    """
    Retrieves the latest inventory availability signal for a product.

    Used by Discovery context for availability filtering and by
    the MCP resource endpoint for inventory lookups.
    """

    def __init__(self, inventory_port: InventoryPort) -> None:
        self._inventory_port = inventory_port

    async def execute(
        self, product_id: str, tenant_id: str
    ) -> QueryResult[InventoryDTO]:
        """
        Query inventory availability for a specific product.

        Args:
            product_id: The product to query.
            tenant_id: The tenant scope.

        Returns:
            QueryResult containing an InventoryDTO on success,
            or empty result if no inventory signal exists.
        """
        try:
            tid = TenantId(value=tenant_id)
            signal = await self._inventory_port.get_availability(product_id, tid)

            if signal is None:
                return QueryResult.empty()

            dto = InventoryDTO(
                product_id=signal.product_id,
                tenant_id=signal.tenant_id.value,
                available_quantity=signal.available_quantity,
                location=signal.location,
                fulfilment_options=[opt.value for opt in signal.fulfilment_options],
                is_in_stock=signal.is_in_stock,
                last_updated=signal.last_updated,
            )

            return QueryResult.ok(dto)

        except ValueError as exc:
            return QueryResult.fail(f"Validation error: {exc}")
        except Exception as exc:
            return QueryResult.fail(f"Inventory query failed: {exc}")
