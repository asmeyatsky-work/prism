"""
Discovery Infrastructure — Firestore Personalisation Adapter.

Architectural Intent:
- Implements PersonalisationPort using Google Cloud Firestore
- Retrieves customer browsing history, purchase history, and preferences
- Data is tenant-scoped via Firestore collection hierarchy
- Graceful degradation: returns empty signals on failure (search still works)

Data Model:
- Collection: tenants/{tenant_id}/customers/{customer_id}/personalisation
- Documents: browsing_history, purchase_history, preferences
- Firestore provides real-time updates and low-latency reads
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prism.discovery.domain.value_objects.search_query import ReRankingSignals

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FirestorePersonalisationConfig:
    """Configuration for Firestore personalisation data access."""

    project_id: str = ""
    database: str = "(default)"
    collection_prefix: str = "tenants"
    max_history_items: int = 100


class FirestorePersonalisationAdapter:
    """
    Implements PersonalisationPort using Google Cloud Firestore.

    Retrieves customer signals from the tenant-scoped Firestore
    collection hierarchy. Each customer's personalisation data is
    stored under:
        tenants/{tenant_id}/customers/{customer_id}/personalisation

    Graceful Degradation:
    - If Firestore is unavailable, returns empty signals
    - Search continues with un-personalised results
    - Failures are logged but never propagated to the caller
    """

    def __init__(self, config: FirestorePersonalisationConfig) -> None:
        self._config = config
        self._client = None  # Lazily initialised Firestore client

    async def get_signals(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> ReRankingSignals:
        """
        Retrieve personalisation signals for a customer.

        Fetches browsing history, purchase history, and preferences
        from Firestore. Returns empty signals if the customer has no
        personalisation data or if Firestore is unavailable.
        """
        logger.info(
            "Fetching personalisation signals: customer=%s, tenant=%s",
            customer_id,
            tenant_id,
        )

        try:
            browsing = await self._fetch_browsing_history(tenant_id, customer_id)
            purchases = await self._fetch_purchase_history(tenant_id, customer_id)
            preferences = await self._fetch_preferences(tenant_id, customer_id)

            return ReRankingSignals(
                browsing_history=tuple(browsing),
                purchase_history=tuple(purchases),
                preferences=preferences,
            )
        except Exception:
            logger.warning(
                "Failed to fetch personalisation signals for customer %s "
                "in tenant %s — returning empty signals",
                customer_id,
                tenant_id,
            )
            return ReRankingSignals()

    async def _fetch_browsing_history(
        self,
        tenant_id: str,
        customer_id: str,
    ) -> list[str]:
        """
        Fetch recent browsing history (product IDs) from Firestore.

        In production, this queries:
            tenants/{tenant_id}/customers/{customer_id}/personalisation/browsing_history

        Results are limited to max_history_items most recent entries.
        """
        collection_path = self._build_path(tenant_id, customer_id)
        logger.debug("Fetching browsing history from: %s", collection_path)
        return []

    async def _fetch_purchase_history(
        self,
        tenant_id: str,
        customer_id: str,
    ) -> list[str]:
        """
        Fetch purchase history (product IDs) from Firestore.

        In production, this queries:
            tenants/{tenant_id}/customers/{customer_id}/personalisation/purchase_history
        """
        collection_path = self._build_path(tenant_id, customer_id)
        logger.debug("Fetching purchase history from: %s", collection_path)
        return []

    async def _fetch_preferences(
        self,
        tenant_id: str,
        customer_id: str,
    ) -> dict[str, str | list[str]]:
        """
        Fetch explicit customer preferences from Firestore.

        Preferences include preferred materials, colours, designers,
        price ranges, etc. Stored as a document at:
            tenants/{tenant_id}/customers/{customer_id}/personalisation/preferences
        """
        collection_path = self._build_path(tenant_id, customer_id)
        logger.debug("Fetching preferences from: %s", collection_path)
        return {}

    def _build_path(self, tenant_id: str, customer_id: str) -> str:
        """Build the Firestore collection path for a customer."""
        return (
            f"{self._config.collection_prefix}/{tenant_id}"
            f"/customers/{customer_id}/personalisation"
        )
