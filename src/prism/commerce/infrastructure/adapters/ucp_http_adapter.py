"""
Commerce Infrastructure — UCP HTTP Adapter

Architectural Intent:
- httpx-based implementation of UCPInboundPort and UCPOutboundPort.
- Behind a feature flag (PRISM_UCP_HTTP_ENABLED): when off, bootstrap should
  prefer the in-memory mock so the demo remains self-contained.
- Every external call has a timeout (Rules §4) and a small bounded retry on
  transient 5xx / network errors. No unbounded waits.
- Bearer auth via Secret Manager-injected env var PRISM_UCP_API_KEY (Rules §4
  forbids literal secrets in code/config).

Layer: infrastructure
Implements: UCPInboundPort, UCPOutboundPort
Stack: canonical (httpx).
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import httpx

from prism.commerce.domain.entities.commerce_event import (
    CommerceEvent,
    CommerceEventSource,
    CommerceEventType,
    ProcessingStatus,
)
from prism.commerce.domain.value_objects.ucp_schema import UCPEventEnvelope
from prism.shared.domain.value_objects import TenantId
from prism.shared.infrastructure.observability import current_correlation_id

logger = logging.getLogger("prism.commerce.ucp_http")


_EVENT_TYPE_MAP: dict[str, CommerceEventType] = {
    "product.created": CommerceEventType.PRODUCT_CREATED,
    "product.updated": CommerceEventType.PRODUCT_UPDATED,
    "inventory.changed": CommerceEventType.INVENTORY_CHANGED,
    "price.changed": CommerceEventType.PRICE_CHANGED,
    "order.placed": CommerceEventType.ORDER_PLACED,
}


def ucp_http_enabled() -> bool:
    """True iff PRISM_UCP_HTTP_ENABLED is set to a truthy value."""
    return os.environ.get("PRISM_UCP_HTTP_ENABLED", "").lower() in {"1", "true", "yes"}


class UCPHttpAdapter:
    """
    HTTP adapter for the Unified Commerce Platform.

    Inbound: idempotency by event_id (in-memory set; production should use
    Redis or Firestore for distributed dedup).
    Outbound: POST PCES payloads to UCP's catalogue endpoint.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout_seconds: float = 10.0,
        max_retries: int = 2,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._processed_event_ids: set[str] = set()
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout_seconds),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "prism-ucp-adapter/0.1",
            },
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    @classmethod
    def from_env(
        cls, *, transport: httpx.AsyncBaseTransport | None = None
    ) -> "UCPHttpAdapter":
        base_url = os.environ.get("PRISM_UCP_BASE_URL", "")
        api_key = os.environ.get("PRISM_UCP_API_KEY", "")
        if not base_url or not api_key:
            raise RuntimeError(
                "PRISM_UCP_BASE_URL and PRISM_UCP_API_KEY must be set when "
                "PRISM_UCP_HTTP_ENABLED=1"
            )
        return cls(base_url=base_url, api_key=api_key, transport=transport)

    # ── UCPInboundPort ───────────────────────────────────────────────

    async def receive_event(self, envelope: UCPEventEnvelope) -> CommerceEvent:
        """
        Acknowledge receipt of a UCP event by calling UCP's ack endpoint, then
        return a domain CommerceEvent. The envelope is authoritative — UCP is
        only contacted to confirm the event was delivered.
        """
        if envelope.event_id in self._processed_event_ids:
            return self._to_commerce_event(envelope, idempotent=True)

        await self._post_with_retry(
            f"/events/{envelope.event_id}/ack",
            json={
                "received_at": datetime.now(UTC).isoformat(),
                "correlation_id": current_correlation_id(),
            },
        )
        self._processed_event_ids.add(envelope.event_id)
        return self._to_commerce_event(envelope, idempotent=False)

    # ── UCPOutboundPort ──────────────────────────────────────────────

    async def push_enriched_product(self, product_data: dict[str, Any]) -> bool:
        """POST an enriched PCES product back to UCP's catalogue API."""
        product_data = {
            **product_data,
            "correlation_id": current_correlation_id(),
        }
        try:
            await self._post_with_retry("/products/enriched", json=product_data)
            return True
        except httpx.HTTPError as exc:
            logger.error("UCP outbound push failed: %s", exc)
            return False

    # ── Internal ─────────────────────────────────────────────────────

    async def _post_with_retry(
        self, path: str, *, json: dict[str, Any]
    ) -> httpx.Response:
        """POST with bounded retry on connect errors and 5xx."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = await self._client.post(path, json=json)
                if resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"UCP {path} returned {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                resp.raise_for_status()
                return resp
            except (httpx.HTTPError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt >= self._max_retries:
                    break
                # exponential backoff: 100ms, 200ms (bounded)
                await asyncio.sleep(0.1 * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def _to_commerce_event(
        self, envelope: UCPEventEnvelope, *, idempotent: bool
    ) -> CommerceEvent:
        event_type = _EVENT_TYPE_MAP.get(
            envelope.event_type, CommerceEventType.PRODUCT_UPDATED
        )
        return CommerceEvent(
            event_type=event_type,
            source=CommerceEventSource.UCP,
            tenant_id=TenantId(value=envelope.source or "default"),
            payload=envelope.payload,
            processing_status=ProcessingStatus.RECEIVED,
        )
