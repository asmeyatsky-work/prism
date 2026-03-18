"""
Commerce Domain Entity — GoogleShoppingFeed

Architectural Intent:
- Tracks the state of a Google Merchant Center product feed for a tenant
- Immutable entity — sync operations return new instances
- Quality score reflects feed data completeness and compliance
- Tenant-scoped: each luxury brand has its own Merchant Center feed

Sync Lifecycle:
  create -> SYNCING -> SYNCED (success) | ERROR (failure)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import Enum

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import TenantId


class FeedSyncStatus(str, Enum):
    """Synchronisation status of a Google Shopping feed."""

    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    ERROR = "ERROR"


@dataclass(frozen=True)
class GoogleShoppingFeed(Entity):
    """
    Tracks a Google Merchant Center product feed for a single tenant.

    Each tenant (luxury brand) maintains one or more feeds in Google Merchant
    Center. This entity tracks sync state, product count, and data quality.

    Attributes:
        tenant_id: The brand this feed belongs to.
        feed_id: Google Merchant Center feed identifier.
        product_count: Number of products in this feed.
        last_sync: Timestamp of the last successful sync.
        sync_status: Current synchronisation state.
        quality_score: Feed data quality score (0.0 to 1.0).
    """

    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="default"))
    feed_id: str = ""
    product_count: int = 0
    last_sync: datetime = field(default_factory=lambda: datetime.now(UTC))
    sync_status: FeedSyncStatus = FeedSyncStatus.SYNCING
    quality_score: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {self.quality_score}"
            )

    def mark_syncing(self, product_count: int) -> GoogleShoppingFeed:
        """Begin a new sync cycle with the given product count."""
        return replace(
            self,
            sync_status=FeedSyncStatus.SYNCING,
            product_count=product_count,
            **self._touch(),
        )

    def mark_synced(self, quality_score: float) -> GoogleShoppingFeed:
        """Mark the feed as successfully synced with updated quality score."""
        if self.sync_status != FeedSyncStatus.SYNCING:
            raise ValueError(
                f"Cannot mark SYNCED from {self.sync_status.value}"
            )
        if not 0.0 <= quality_score <= 1.0:
            raise ValueError(
                f"quality_score must be between 0.0 and 1.0, got {quality_score}"
            )
        return replace(
            self,
            sync_status=FeedSyncStatus.SYNCED,
            quality_score=quality_score,
            last_sync=datetime.now(UTC),
            **self._touch(),
        )

    def mark_error(self) -> GoogleShoppingFeed:
        """Mark the feed sync as failed."""
        if self.sync_status != FeedSyncStatus.SYNCING:
            raise ValueError(
                f"Cannot mark ERROR from {self.sync_status.value}"
            )
        return replace(
            self,
            sync_status=FeedSyncStatus.ERROR,
            **self._touch(),
        )
