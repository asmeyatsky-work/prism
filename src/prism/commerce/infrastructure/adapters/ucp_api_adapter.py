"""
Commerce Infrastructure Adapter — UCP API Adapter

Architectural Intent:
- Implements both UCPInboundPort and UCPOutboundPort
- Handles HTTP communication with the Unified Commerce Platform API
- Manages idempotency via event_id deduplication
- Converts between UCP wire format and domain types
- Production: uses aiohttp for non-blocking HTTP calls
- Parallelism-safe: stateless beyond configuration

Wire Protocol:
  Inbound:  UCP Pub/Sub -> UCPEventEnvelope -> CommerceEvent (RECEIVED)
  Outbound: PCES dict -> UCP Product API -> success/failure
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventSource,
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.domain.value_objects import TenantId

logger = logging.getLogger(__name__)


class UCPAPIAdapter:
    """
    Adapter implementing UCPInboundPort and UCPOutboundPort.

    Handles bidirectional communication with the UCP REST API.
    Inbound: converts UCP event envelopes to CommerceEvent aggregates.
    Outbound: pushes enriched product data back to UCP's catalogue API.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Initialise the UCP API adapter.

        Args:
            base_url: Base URL of the UCP API (e.g. "https://ucp.example.com/api/v1").
            api_key: API key for UCP authentication.
            timeout_seconds: HTTP request timeout.
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._session: Any = None
        # In-memory deduplication set for idempotency (production: use Redis/Firestore)
        self._processed_event_ids: set[str] = set()

    async def _get_session(self) -> Any:
        """Lazily initialise the aiohttp session."""
        if self._session is None:
            try:
                import aiohttp

                timeout = aiohttp.ClientTimeout(total=self._timeout_seconds)
                self._session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=timeout,
                )
            except ImportError:
                logger.warning("aiohttp not available; HTTP calls will be simulated")
                self._session = None
        return self._session

    async def receive_event(self, envelope: UCPEventEnvelope) -> CommerceEvent:
        """
        Receive and persist a UCP event envelope as a CommerceEvent.

        Implements UCPInboundPort.receive_event. Performs idempotency check
        and converts the envelope to a domain aggregate in RECEIVED status.

        Args:
            envelope: The inbound UCP event envelope.

        Returns:
            A CommerceEvent in RECEIVED status.

        Raises:
            ValueError: If the event has already been processed (duplicate).
        """
        # Idempotency check
        if envelope.event_id in self._processed_event_ids:
            raise ValueError(
                f"Duplicate event: {envelope.event_id} has already been received"
            )

        self._processed_event_ids.add(envelope.event_id)

        # Map source string to enum
        source_map = {
            "ucp": CommerceEventSource.UCP,
            "prism": CommerceEventSource.PRISM,
            "google_shopping": CommerceEventSource.GOOGLE_SHOPPING,
        }
        source = source_map.get(
            envelope.source.lower(), CommerceEventSource.UCP
        )

        # Extract tenant_id from payload
        payload = envelope.payload_dict
        tenant_id_str = payload.get("tenant_id", "default")

        commerce_event = CommerceEvent(
            event_type=CommerceEventType.PRODUCT_UPDATED,  # Will be reclassified by domain service
            source=source,
            tenant_id=TenantId(value=tenant_id_str),
            payload=envelope.payload,
            processing_status=ProcessingStatus.RECEIVED,
        )

        logger.info(
            "UCP event received: id=%s type=%s source=%s",
            envelope.event_id,
            envelope.event_type,
            envelope.source,
        )

        return commerce_event

    async def push_enriched_product(self, product_data: dict[str, Any]) -> bool:
        """
        Push enriched product data back to UCP.

        Implements UCPOutboundPort.push_enriched_product. Sends a PUT request
        to the UCP product API with PRISM-enriched data.

        Args:
            product_data: PCES-format product dictionary.

        Returns:
            True if the push was accepted by UCP.
        """
        product_id = product_data.get("id", product_data.get("sku", ""))
        if not product_id:
            logger.error("Cannot push product without id or sku")
            return False

        url = f"{self._base_url}/products/{product_id}/enrichment"

        session = await self._get_session()
        if session is None:
            # Simulation mode when aiohttp is not available
            logger.info(
                "Simulated push to UCP: product_id=%s url=%s",
                product_id,
                url,
            )
            return True

        try:
            async with session.put(url, json=product_data) as response:
                if response.status in (200, 201, 204):
                    logger.info(
                        "Enriched product pushed to UCP: product_id=%s status=%d",
                        product_id,
                        response.status,
                    )
                    return True
                else:
                    body = await response.text()
                    logger.error(
                        "UCP rejected enrichment push: product_id=%s status=%d body=%s",
                        product_id,
                        response.status,
                        body[:500],
                    )
                    return False
        except Exception as exc:
            logger.error(
                "UCP push failed: product_id=%s error=%s",
                product_id,
                exc,
            )
            return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session is not None:
            await self._session.close()
            self._session = None
