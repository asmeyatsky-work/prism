"""
Commerce Domain Ports — Protocol-Based Contracts

Architectural Intent:
- Ports define the domain's requirements from infrastructure without coupling to it
- All ports are typing.Protocol classes — adapters implement them structurally
- Async-first: all port methods are coroutines for parallelism-first design
- Tenant-scoped operations enforce multi-tenant isolation at the domain boundary
- Per skill2026 Rule 2: MCP tool schemas mirror port method signatures

Port Catalogue:
  UCPInboundPort    — Receive and persist inbound UCP events
  UCPOutboundPort   — Push enriched data back to UCP
  GoogleShoppingPort — Publish and monitor Google Merchant Center feeds
  InventoryPort     — Read and write inventory availability signals
"""

from __future__ import annotations

from typing import Any, Protocol

from prism.commerce.domain.entities.commerce_event import CommerceEvent
from prism.commerce.domain.entities.inventory_signal import InventorySignal
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.domain.value_objects import TenantId


class UCPInboundPort(Protocol):
    """
    Port for receiving inbound UCP events.

    Infrastructure adapters implementing this port handle deserialisation,
    idempotency checks, and persistence of raw UCP events before domain
    processing begins.
    """

    async def receive_event(self, envelope: UCPEventEnvelope) -> CommerceEvent:
        """
        Receive and persist a UCP event envelope.

        Creates a CommerceEvent aggregate from the envelope and persists it
        in RECEIVED status. Returns the persisted event for downstream processing.

        Args:
            envelope: The inbound UCP event envelope.

        Returns:
            A persisted CommerceEvent in RECEIVED status.
        """
        ...


class UCPOutboundPort(Protocol):
    """
    Port for pushing enriched data back to UCP.

    The outbound port writes PRISM-enriched product data to the UCP's
    product catalogue API, completing the bidirectional data flow.
    """

    async def push_enriched_product(self, product_data: dict[str, Any]) -> bool:
        """
        Push enriched product data back to the UCP.

        Args:
            product_data: PCES-format product data to push.

        Returns:
            True if the push was successful, False otherwise.
        """
        ...


class GoogleShoppingPort(Protocol):
    """
    Port for Google Merchant Center feed operations.

    Manages publishing enriched product data as structured feeds and
    monitoring feed synchronisation status.
    """

    async def publish_feed(
        self, products: list[dict[str, Any]], tenant_id: TenantId
    ) -> str:
        """
        Publish a product feed to Google Merchant Center.

        Args:
            products: List of PCES-format product dicts for the feed.
            tenant_id: The tenant (brand) this feed belongs to.

        Returns:
            The Google Merchant Center feed ID.
        """
        ...

    async def get_feed_status(self, feed_id: str) -> dict[str, Any]:
        """
        Retrieve the current status of a Google Shopping feed.

        Args:
            feed_id: The Google Merchant Center feed identifier.

        Returns:
            Feed status information including sync state and diagnostics.
        """
        ...


class InventoryPort(Protocol):
    """
    Port for inventory availability operations.

    Provides read/write access to inventory signals, supporting
    real-time availability for discovery and feed publishing.
    """

    async def get_availability(
        self, product_id: str, tenant_id: TenantId
    ) -> InventorySignal | None:
        """
        Retrieve the latest inventory signal for a product.

        Args:
            product_id: The product to query availability for.
            tenant_id: The tenant scope.

        Returns:
            The latest InventorySignal, or None if no signal exists.
        """
        ...

    async def update_availability(self, signal: InventorySignal) -> None:
        """
        Persist an updated inventory signal.

        Replaces the previous signal for this product/location combination.

        Args:
            signal: The new inventory signal to persist.
        """
        ...
