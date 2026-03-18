"""
Commerce Application Query — Get Google Shopping Feed Status

Architectural Intent:
- Read-side query for retrieving Google Shopping feed synchronisation status
- Returns FeedStatusDTO for serialisation at the presentation boundary
- Delegates to GoogleShoppingPort for feed status retrieval
- Returns QueryResult for consistent success/failure semantics
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from prism.commerce.application.dtos.commerce_dto import FeedStatusDTO
from prism.commerce.domain.ports.commerce_ports import GoogleShoppingPort
from prism.shared.application.dtos import QueryResult


class GetGoogleShoppingFeedStatusQuery:
    """
    Retrieves the current synchronisation status of a Google Shopping feed.

    Used for monitoring feed health and diagnosing sync issues.
    Exposed via MCP resource: commerce://feed/{tenant_id}.
    """

    def __init__(self, google_shopping_port: GoogleShoppingPort) -> None:
        self._google_shopping = google_shopping_port

    async def execute(self, feed_id: str) -> QueryResult[FeedStatusDTO]:
        """
        Query the status of a Google Shopping feed.

        Args:
            feed_id: The Google Merchant Center feed identifier.

        Returns:
            QueryResult containing a FeedStatusDTO on success,
            or an error description on failure.
        """
        try:
            status = await self._google_shopping.get_feed_status(feed_id)

            if not status:
                return QueryResult.empty()

            # Parse last_sync timestamp if present
            last_sync: datetime | None = None
            raw_last_sync = status.get("last_sync")
            if isinstance(raw_last_sync, datetime):
                last_sync = raw_last_sync
            elif isinstance(raw_last_sync, str):
                try:
                    last_sync = datetime.fromisoformat(raw_last_sync)
                except ValueError:
                    last_sync = None

            dto = FeedStatusDTO(
                feed_id=status.get("feed_id", feed_id),
                tenant_id=status.get("tenant_id", ""),
                product_count=int(status.get("product_count", 0)),
                sync_status=status.get("sync_status", ""),
                quality_score=float(status.get("quality_score", 0.0)),
                last_sync=last_sync,
            )

            return QueryResult.ok(dto)

        except Exception as exc:
            return QueryResult.fail(f"Feed status query failed: {exc}")
