"""
Commerce Orchestration — Commerce Sync Workflow

Architectural Intent:
- DAG-based workflow for end-to-end commerce event processing
- Parallelism-first: update_inventory and trigger_enrichment run concurrently
- Uses the shared DAGOrchestrator for dependency-aware parallel execution
- Per skill2026 Principle 6: steps at the same topological level run via asyncio.gather

DAG Topology:
  receive_event
       │
  classify_event (depends on: receive_event)
       │
  ┌────┴────┐
  │         │
  update_inventory    trigger_enrichment   (parallel, depend on: classify_event)
  │         │
  └────┬────┘
       │
  push_to_google_shopping (depends on: update_inventory, trigger_enrichment)
"""

from __future__ import annotations

from typing import Any

from prism.commerce.domain.entities.commerce_event import CommerceEventSource, CommerceEventType
from prism.commerce.domain.ports.commerce_ports import (
    GoogleShoppingPort,
    InventoryPort,
    UCPInboundPort,
)
from prism.commerce.domain.services.event_processing_service import EventProcessingService
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.application.orchestration import (
    DAGOrchestrator,
    StepResult,
    WorkflowStep,
)
from prism.shared.domain.value_objects import TenantId


class CommerceSyncWorkflow:
    """
    End-to-end workflow for processing a UCP commerce event.

    Orchestrates receiving, classifying, processing (with parallel inventory
    update and enrichment trigger), and Google Shopping feed publishing.

    The workflow uses DAGOrchestrator to automatically parallelise independent
    steps and enforce dependency ordering.
    """

    def __init__(
        self,
        ucp_inbound_port: UCPInboundPort,
        inventory_port: InventoryPort,
        google_shopping_port: GoogleShoppingPort,
        event_processing_service: EventProcessingService,
    ) -> None:
        self._ucp_inbound = ucp_inbound_port
        self._inventory_port = inventory_port
        self._google_shopping = google_shopping_port
        self._event_service = event_processing_service

    def build_orchestrator(self) -> DAGOrchestrator:
        """
        Construct the DAG orchestrator with all workflow steps wired.

        Returns:
            A configured DAGOrchestrator ready for execution.
        """
        steps = [
            WorkflowStep(
                name="receive_event",
                execute=self._receive_event,
                depends_on=(),
                is_critical=True,
                timeout_seconds=10.0,
            ),
            WorkflowStep(
                name="classify_event",
                execute=self._classify_event,
                depends_on=("receive_event",),
                is_critical=True,
                timeout_seconds=5.0,
            ),
            WorkflowStep(
                name="update_inventory",
                execute=self._update_inventory,
                depends_on=("classify_event",),
                is_critical=False,
                timeout_seconds=15.0,
            ),
            WorkflowStep(
                name="trigger_enrichment",
                execute=self._trigger_enrichment,
                depends_on=("classify_event",),
                is_critical=False,
                timeout_seconds=30.0,
            ),
            WorkflowStep(
                name="push_to_google_shopping",
                execute=self._push_to_google_shopping,
                depends_on=("update_inventory", "trigger_enrichment"),
                is_critical=False,
                timeout_seconds=30.0,
            ),
        ]
        return DAGOrchestrator(steps)

    async def run(self, event_data: dict[str, Any]) -> dict[str, StepResult]:
        """
        Execute the full commerce sync workflow for a UCP event.

        Args:
            event_data: Raw UCP event data dictionary.

        Returns:
            Dict mapping step names to their StepResults.
        """
        orchestrator = self.build_orchestrator()
        context = {"event_data": event_data}
        return await orchestrator.execute(context)

    async def _receive_event(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Receive and persist the UCP event."""
        event_data = context["event_data"]
        envelope = UCPEventEnvelope.from_dict(event_data)
        commerce_event = await self._ucp_inbound.receive_event(envelope)
        return {
            "commerce_event": commerce_event,
            "envelope": envelope,
        }

    async def _classify_event(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Classify the event type using the domain service."""
        receive_result = dep_results.get("receive_event", {})
        envelope = receive_result.get("envelope")
        commerce_event = receive_result.get("commerce_event")

        if envelope is None:
            raise ValueError("No envelope available from receive_event step")

        event_type = self._event_service.classify_event(envelope)

        return {
            "commerce_event": commerce_event,
            "envelope": envelope,
            "event_type": event_type,
        }

    async def _update_inventory(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Update inventory signals if the event contains inventory data."""
        classify_result = dep_results.get("classify_event", {})
        event_type = classify_result.get("event_type")
        envelope: UCPEventEnvelope | None = classify_result.get("envelope")

        if event_type != CommerceEventType.INVENTORY_CHANGED or envelope is None:
            return {"skipped": True, "reason": "Not an inventory event"}

        payload = envelope.payload_dict
        from prism.commerce.domain.entities.inventory_signal import (
            FulfilmentOption,
            InventorySignal,
        )

        # Parse fulfilment options from payload
        raw_options = payload.get("fulfilment_options", ["SHIP"])
        fulfilment_options: list[FulfilmentOption] = []
        for opt in raw_options:
            try:
                fulfilment_options.append(FulfilmentOption(opt))
            except ValueError:
                continue
        if not fulfilment_options:
            fulfilment_options = [FulfilmentOption.SHIP]

        signal = InventorySignal(
            product_id=payload.get("product_id", ""),
            tenant_id=TenantId(value=payload.get("tenant_id", "default")),
            available_quantity=int(payload.get("available_quantity", 0)),
            location=payload.get("location", ""),
            fulfilment_options=tuple(fulfilment_options),
        )
        await self._inventory_port.update_availability(signal)
        return {"signal": signal, "updated": True}

    async def _trigger_enrichment(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Trigger AI enrichment for product events.

        In production, this would publish an enrichment request to the Catalogue
        context via Pub/Sub. For now, returns enrichment metadata placeholder.
        """
        classify_result = dep_results.get("classify_event", {})
        event_type = classify_result.get("event_type")
        envelope: UCPEventEnvelope | None = classify_result.get("envelope")

        enrichment_types = (
            CommerceEventType.PRODUCT_CREATED,
            CommerceEventType.PRODUCT_UPDATED,
        )
        if event_type not in enrichment_types:
            return {"skipped": True, "reason": "Event type does not require enrichment"}

        # In production, this publishes to the Catalogue context enrichment pipeline.
        # The enrichment result would arrive asynchronously.
        payload = envelope.payload_dict if envelope else {}
        return {
            "enrichment_requested": True,
            "product_id": payload.get("id", ""),
            "event_type": event_type.value if event_type else "",
        }

    async def _push_to_google_shopping(
        self,
        context: dict[str, Any],
        dep_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Push enriched product data to Google Shopping feed."""
        enrichment_result = dep_results.get("trigger_enrichment", {})
        classify_result = dep_results.get("classify_event", {})
        envelope: UCPEventEnvelope | None = classify_result.get("envelope")

        if enrichment_result.get("skipped"):
            return {"skipped": True, "reason": "No enrichment data to publish"}

        if envelope is None:
            return {"skipped": True, "reason": "No envelope available"}

        payload = envelope.payload_dict
        tenant_id_str = payload.get("tenant_id", "default")
        tid = TenantId(value=tenant_id_str)

        # Build minimal feed product from available data
        feed_product = {
            "id": payload.get("id", ""),
            "name": payload.get("name", ""),
            "brand": payload.get("brand", ""),
            "price": payload.get("price"),
            "images": payload.get("images", []),
        }

        feed_id = await self._google_shopping.publish_feed([feed_product], tid)
        return {"feed_id": feed_id, "published": True}
