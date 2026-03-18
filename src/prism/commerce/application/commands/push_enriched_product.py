"""
Commerce Application Command — Push Enriched Product

Architectural Intent:
- Use case for pushing PRISM-enriched product data back to UCP
- Completes the bidirectional data flow: UCP -> PRISM enrichment -> UCP
- Transforms internal PCES schema to UCP-compatible format
- Emits EnrichedProductPushedEvent on successful push
- UCPOutboundPort handles the actual API communication

Flow:
  1. Receive PCES-format enriched product data
  2. Push to UCP via UCPOutboundPort
  3. Emit EnrichedProductPushedEvent
"""

from __future__ import annotations

from typing import Any

from prism.commerce.domain.events.commerce_events import EnrichedProductPushedEvent
from prism.commerce.domain.ports.commerce_ports import UCPOutboundPort
from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort


class PushEnrichedProductUseCase:
    """
    Pushes PRISM-enriched product data back to the Unified Commerce Platform.

    This use case is the outbound leg of the commerce data loop. After AI
    enrichment in the Catalogue context, enriched data flows back to UCP
    so the source system benefits from PRISM's intelligence.
    """

    def __init__(
        self,
        ucp_outbound_port: UCPOutboundPort,
        event_bus: EventBusPort,
    ) -> None:
        self._ucp_outbound = ucp_outbound_port
        self._event_bus = event_bus

    async def execute(
        self, product_data: dict[str, Any]
    ) -> CommandResult[bool]:
        """
        Push enriched product data to UCP.

        Args:
            product_data: PCES-format enriched product dictionary. Must contain
                at least 'id' or 'sku' for UCP to identify the product.

        Returns:
            CommandResult containing True on success, or an error on failure.
        """
        try:
            product_id = product_data.get("id", "")
            sku = product_data.get("sku", "")
            tenant_id = product_data.get("tenant_id", "")

            if not product_id and not sku:
                return CommandResult.fail(
                    error="Product data must contain 'id' or 'sku'",
                    code="MISSING_IDENTIFIER",
                )

            # Push to UCP
            success = await self._ucp_outbound.push_enriched_product(product_data)

            if not success:
                return CommandResult.fail(
                    error="UCP rejected the enriched product data",
                    code="UCP_REJECTION",
                )

            # Emit domain event
            event = EnrichedProductPushedEvent(
                aggregate_id=product_id or sku,
                tenant_id=tenant_id,
                product_id=product_id,
                sku=sku,
                enrichment_version=product_data.get("enrichment_version", ""),
                quality_score=float(product_data.get("quality_score", 0.0)),
            )
            await self._event_bus.publish([event])

            return CommandResult.ok(True)

        except Exception as exc:
            return CommandResult.fail(
                error=f"Push to UCP failed: {exc}",
                code="PUSH_ERROR",
            )
