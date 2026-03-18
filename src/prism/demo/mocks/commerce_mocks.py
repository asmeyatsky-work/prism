"""
Commerce Context — Mock UCP, Google Shopping, and Inventory Adapters

Provides mock implementations of:
- UCPInboundPort       -> MockUCPInbound
- UCPOutboundPort      -> MockUCPOutbound
- GoogleShoppingPort   -> MockGoogleShopping
- InventoryPort        -> MockInventory

MockInventory maintains per-product stock levels with realistic quantities
for luxury retail (low stock counts reflecting exclusivity).
"""

from __future__ import annotations

import logging
import random
import uuid
from datetime import UTC, datetime
from typing import Any

from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventSource,
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.entities.inventory_signal import (
    FulfilmentOption,
    InventorySignal,
)
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.domain.value_objects import TenantId

logger = logging.getLogger("prism.demo.commerce")


class MockUCPInbound:
    """
    Mock UCP inbound port that converts event envelopes into CommerceEvent
    aggregates in RECEIVED status. Maintains an in-memory event store for
    idempotency checks.
    """

    def __init__(self) -> None:
        self._received_events: dict[str, CommerceEvent] = {}

    async def receive_event(self, envelope: UCPEventEnvelope) -> CommerceEvent:
        # Idempotency: return existing event if already received
        if envelope.event_id in self._received_events:
            return self._received_events[envelope.event_id]

        # Map UCP event type string to domain enum
        event_type_map: dict[str, CommerceEventType] = {
            "product.created": CommerceEventType.PRODUCT_CREATED,
            "product.updated": CommerceEventType.PRODUCT_UPDATED,
            "inventory.changed": CommerceEventType.INVENTORY_CHANGED,
            "price.changed": CommerceEventType.PRICE_CHANGED,
            "order.placed": CommerceEventType.ORDER_PLACED,
        }
        event_type = event_type_map.get(
            envelope.event_type,
            CommerceEventType.PRODUCT_UPDATED,
        )

        commerce_event = CommerceEvent(
            event_type=event_type,
            source=CommerceEventSource.UCP,
            tenant_id=TenantId(value=envelope.source or "demo"),
            payload=envelope.payload,
            processing_status=ProcessingStatus.RECEIVED,
        )

        self._received_events[envelope.event_id] = commerce_event
        logger.info(
            "UCP event received: %s [%s]",
            envelope.event_id,
            event_type.value,
        )
        return commerce_event


class MockUCPOutbound:
    """
    Mock UCP outbound port that logs enriched product pushes.
    Always returns success. Stores pushed data for inspection.
    """

    def __init__(self) -> None:
        self._pushed_products: list[dict[str, Any]] = []

    async def push_enriched_product(self, product_data: dict[str, Any]) -> bool:
        self._pushed_products.append(product_data)
        logger.info(
            "Enriched product pushed to UCP: %s (%s)",
            product_data.get("name", "unknown"),
            product_data.get("sku", "no-sku"),
        )
        return True

    @property
    def pushed_products(self) -> list[dict[str, Any]]:
        """Access pushed product data for testing/inspection."""
        return list(self._pushed_products)


class MockGoogleShopping:
    """
    Mock Google Merchant Center connector. Generates realistic feed IDs
    and returns mock feed status with healthy diagnostics.
    """

    def __init__(self) -> None:
        self._feeds: dict[str, dict[str, Any]] = {}

    async def publish_feed(
        self,
        products: list[dict[str, Any]],
        tenant_id: TenantId,
    ) -> str:
        feed_id = f"gmc_{tenant_id.value}_{uuid.uuid4().hex[:8]}"
        self._feeds[feed_id] = {
            "feed_id": feed_id,
            "tenant_id": tenant_id.value,
            "product_count": len(products),
            "status": "ACTIVE",
            "created_at": datetime.now(UTC).isoformat(),
            "last_sync": datetime.now(UTC).isoformat(),
        }
        logger.info(
            "Google Shopping feed published: %s (%d products)",
            feed_id,
            len(products),
        )
        return feed_id

    async def get_feed_status(self, feed_id: str) -> dict[str, Any]:
        if feed_id in self._feeds:
            feed = self._feeds[feed_id]
            return {
                "feed_id": feed_id,
                "status": "ACTIVE",
                "product_count": feed["product_count"],
                "approved_count": feed["product_count"],
                "disapproved_count": 0,
                "pending_count": 0,
                "last_sync": feed["last_sync"],
                "diagnostics": {
                    "data_quality_score": 0.94,
                    "issues": [],
                },
            }
        return {
            "feed_id": feed_id,
            "status": "NOT_FOUND",
            "diagnostics": {"error": "Feed not found"},
        }


# ── Pre-seeded inventory for luxury product demo ───────────────────────

_DEMO_INVENTORY: dict[str, dict[str, Any]] = {
    "prod_gucci_diana_001": {"quantity": 12, "location": "Milan Warehouse"},
    "prod_gucci_horsebit_002": {"quantity": 8, "location": "Milan Warehouse"},
    "prod_lv_capucines_003": {"quantity": 5, "location": "Paris Atelier"},
    "prod_hermes_birkin_004": {"quantity": 2, "location": "Paris Faubourg"},
    "prod_dior_saddle_005": {"quantity": 15, "location": "Paris Warehouse"},
    "prod_bottega_cassette_006": {"quantity": 7, "location": "Vicenza Atelier"},
    "prod_chanel_classic_007": {"quantity": 3, "location": "Paris Rue Cambon"},
    "prod_prada_galleria_008": {"quantity": 10, "location": "Milan Warehouse"},
    "prod_gucci_ace_009": {"quantity": 25, "location": "Florence DC"},
    "prod_lv_archlight_010": {"quantity": 18, "location": "Paris Warehouse"},
    "prod_louboutin_kate_011": {"quantity": 14, "location": "Paris Warehouse"},
    "prod_gucci_flora_012": {"quantity": 6, "location": "Milan Warehouse"},
    "prod_valentino_gown_013": {"quantity": 4, "location": "Rome Atelier"},
    "prod_burberry_trench_014": {"quantity": 20, "location": "London Warehouse"},
    "prod_maxmara_teddy_015": {"quantity": 11, "location": "Reggio Emilia DC"},
    "prod_cartier_tank_016": {"quantity": 3, "location": "Geneva Vault"},
    "prod_rolex_datejust_017": {"quantity": 1, "location": "Geneva Vault"},
    "prod_hermes_carre_018": {"quantity": 30, "location": "Lyon Workshop"},
    "prod_celine_triomphe_019": {"quantity": 16, "location": "Paris Warehouse"},
    "prod_tiffany_pendant_020": {"quantity": 22, "location": "New York Vault"},
}


class MockInventory:
    """
    In-memory inventory with pre-seeded luxury product stock levels.
    Quantities reflect realistic luxury retail patterns: limited editions
    have very low stock (1-5), accessories are more available (15-30).
    """

    def __init__(self) -> None:
        self._signals: dict[str, InventorySignal] = {}
        # Seed demo inventory
        for product_id, data in _DEMO_INVENTORY.items():
            self._signals[product_id] = InventorySignal(
                product_id=product_id,
                tenant_id=TenantId(value="demo"),
                available_quantity=data["quantity"],
                location=data["location"],
                fulfilment_options=(
                    FulfilmentOption.SHIP,
                    FulfilmentOption.STORE_PICKUP,
                ),
                last_updated=datetime.now(UTC),
            )

    async def get_availability(
        self,
        product_id: str,
        tenant_id: TenantId,
    ) -> InventorySignal | None:
        # Check pre-seeded and dynamically added inventory
        signal = self._signals.get(product_id)
        if signal:
            return signal

        # For unknown products, generate a random availability signal
        quantity = random.choice([0, 0, 2, 5, 8, 12, 15])
        if quantity == 0:
            return None

        locations = [
            "Milan Warehouse", "Paris Atelier", "London Warehouse",
            "New York Vault", "Tokyo Boutique", "Hong Kong DC",
        ]
        signal = InventorySignal(
            product_id=product_id,
            tenant_id=tenant_id,
            available_quantity=quantity,
            location=random.choice(locations),
            fulfilment_options=(FulfilmentOption.SHIP,),
            last_updated=datetime.now(UTC),
        )
        self._signals[product_id] = signal
        return signal

    async def update_availability(self, signal: InventorySignal) -> None:
        self._signals[signal.product_id] = signal
        logger.info(
            "Inventory updated: %s -> %d units at %s",
            signal.product_id,
            signal.available_quantity,
            signal.location,
        )
