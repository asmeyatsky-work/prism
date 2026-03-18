"""
Commerce Application Command — Sync Google Shopping

Architectural Intent:
- Use case for publishing enriched product feeds to Google Merchant Center
- Transforms PRISM-enriched products to feed format via PCES schema
- Tracks feed sync state via GoogleShoppingFeed entity
- Emits GoogleShoppingFeedSyncedEvent on completion
- Content API interaction delegated to GoogleShoppingPort adapter

Flow:
  1. Retrieve enriched products for the tenant
  2. Transform each product to PCES feed format
  3. Publish feed via GoogleShoppingPort
  4. Update feed entity state (SYNCED or ERROR)
  5. Emit domain event
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from prism.commerce.domain.entities.google_shopping_feed import (
    FeedSyncStatus,
    GoogleShoppingFeed,
)
from prism.commerce.domain.events.commerce_events import (
    GoogleShoppingFeedSyncedEvent,
)
from prism.commerce.domain.ports.commerce_ports import GoogleShoppingPort
from prism.shared.application.dtos import CommandResult
from prism.shared.domain.events import EventBusPort
from prism.shared.domain.value_objects import TenantId


class SyncGoogleShoppingUseCase:
    """
    Publishes enriched product feeds to Google Merchant Center via Content API.

    Accepts a list of PCES-format product dicts and a tenant context, then
    coordinates feed publishing, state tracking, and event emission.
    """

    def __init__(
        self,
        google_shopping_port: GoogleShoppingPort,
        event_bus: EventBusPort,
    ) -> None:
        self._google_shopping = google_shopping_port
        self._event_bus = event_bus

    async def execute(
        self,
        products: list[dict[str, Any]],
        tenant_id: str,
    ) -> CommandResult[GoogleShoppingFeed]:
        """
        Publish enriched products to Google Shopping and track feed state.

        Args:
            products: List of PCES-format product dictionaries.
            tenant_id: The tenant (brand) to publish the feed for.

        Returns:
            CommandResult containing the GoogleShoppingFeed entity on success,
            or an error description on failure.
        """
        try:
            tid = TenantId(value=tenant_id)

            # Create feed entity in SYNCING state
            feed = GoogleShoppingFeed(
                tenant_id=tid,
                product_count=len(products),
                sync_status=FeedSyncStatus.SYNCING,
            )

            # Publish to Google Merchant Center
            feed_id = await self._google_shopping.publish_feed(products, tid)

            # Update feed with returned ID and mark synced
            feed = GoogleShoppingFeed(
                id=feed.id,
                tenant_id=tid,
                feed_id=feed_id,
                product_count=len(products),
                sync_status=FeedSyncStatus.SYNCING,
                created_at=feed.created_at,
            )
            # Calculate quality score based on product data completeness
            quality_score = self._calculate_quality_score(products)
            feed = feed.mark_synced(quality_score=quality_score)

            # Emit domain event
            event = GoogleShoppingFeedSyncedEvent(
                aggregate_id=feed.id,
                tenant_id=tenant_id,
                feed_id=feed_id,
                product_count=len(products),
                quality_score=quality_score,
                sync_status=FeedSyncStatus.SYNCED.value,
            )
            await self._event_bus.publish([event])

            return CommandResult.ok(feed)

        except ValueError as exc:
            return CommandResult.fail(
                error=f"Validation error: {exc}",
                code="VALIDATION_ERROR",
            )
        except Exception as exc:
            return CommandResult.fail(
                error=f"Google Shopping sync failed: {exc}",
                code="SYNC_ERROR",
            )

    @staticmethod
    def _calculate_quality_score(products: list[dict[str, Any]]) -> float:
        """
        Calculate feed quality score based on product data completeness.

        Checks for presence of required fields: name, brand, price, images.
        Returns a score between 0.0 and 1.0.
        """
        if not products:
            return 0.0

        required_fields = ("name", "brand", "price", "images")
        total_score = 0.0

        for product in products:
            field_score = sum(
                1.0
                for f in required_fields
                if product.get(f)
            )
            total_score += field_score / len(required_fields)

        return round(total_score / len(products), 3)
