"""
Gateway Infrastructure — Webhook Dispatcher

Architectural Intent:
- Implements WebhookDispatchPort for delivering events to tenant endpoints
- Signs payloads with HMAC-SHA256 using per-tenant secrets
- Retries with exponential back-off on transient failures
- Logs delivery attempts for audit and debugging
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from prism.shared.domain.value_objects import TenantId
from prism.gateway.domain.ports.gateway_ports import TenantConfigPort

logger = logging.getLogger(__name__)

# Default timeout for webhook delivery (seconds)
_DELIVERY_TIMEOUT = 10.0

# Maximum retry attempts before giving up
_MAX_RETRIES = 3

# Base delay for exponential back-off (seconds)
_BASE_RETRY_DELAY = 1.0


def _compute_signature(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


class WebhookDispatcher:
    """
    Webhook event dispatcher implementing ``WebhookDispatchPort``.

    Delivers JSON payloads to tenant-configured webhook URLs with:
    - HMAC-SHA256 signature in the ``X-Prism-Signature`` header
    - Exponential back-off retry on 5xx responses and network errors
    - Structured logging of every delivery attempt
    """

    def __init__(
        self,
        tenant_config_port: TenantConfigPort,
        http_client: httpx.AsyncClient | None = None,
        webhook_secret: str = "",
    ) -> None:
        self._tenant_config_port = tenant_config_port
        self._http = http_client or httpx.AsyncClient(timeout=_DELIVERY_TIMEOUT)
        self._default_secret = webhook_secret

    async def dispatch(
        self, tenant_id: TenantId, event_type: str, payload: dict[str, Any]
    ) -> bool:
        """
        Dispatch a webhook event to the tenant's registered URL.

        Returns True if delivery was acknowledged (2xx), False otherwise.
        """
        config = await self._tenant_config_port.get_config(tenant_id)
        url = config.get_webhook_url(event_type)

        if not url:
            logger.debug(
                "No webhook URL registered: tenant_id=%s event_type=%s",
                tenant_id.value,
                event_type,
            )
            return False

        envelope = {
            "event_type": event_type,
            "tenant_id": tenant_id.value,
            "timestamp": time.time(),
            "data": payload,
        }
        payload_bytes = json.dumps(envelope, default=str).encode("utf-8")

        secret = self._default_secret or tenant_id.value
        signature = _compute_signature(payload_bytes, secret)

        headers = {
            "Content-Type": "application/json",
            "X-Prism-Signature": f"sha256={signature}",
            "X-Prism-Event": event_type,
            "X-Prism-Tenant": tenant_id.value,
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await self._http.post(
                    url, content=payload_bytes, headers=headers
                )

                if response.status_code < 300:
                    logger.info(
                        "Webhook delivered: tenant_id=%s event=%s url=%s status=%d attempt=%d",
                        tenant_id.value,
                        event_type,
                        url,
                        response.status_code,
                        attempt,
                    )
                    return True

                if response.status_code >= 500:
                    logger.warning(
                        "Webhook server error: tenant_id=%s url=%s status=%d attempt=%d/%d",
                        tenant_id.value,
                        url,
                        response.status_code,
                        attempt,
                        _MAX_RETRIES,
                    )
                else:
                    # 4xx errors are not retried
                    logger.error(
                        "Webhook client error: tenant_id=%s url=%s status=%d",
                        tenant_id.value,
                        url,
                        response.status_code,
                    )
                    return False

            except httpx.TimeoutException:
                logger.warning(
                    "Webhook timeout: tenant_id=%s url=%s attempt=%d/%d",
                    tenant_id.value,
                    url,
                    attempt,
                    _MAX_RETRIES,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "Webhook network error: tenant_id=%s url=%s error=%s attempt=%d/%d",
                    tenant_id.value,
                    url,
                    str(exc),
                    attempt,
                    _MAX_RETRIES,
                )

            # Exponential back-off before retry
            if attempt < _MAX_RETRIES:
                import asyncio

                delay = _BASE_RETRY_DELAY * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

        logger.error(
            "Webhook delivery failed after %d attempts: tenant_id=%s event=%s url=%s",
            _MAX_RETRIES,
            tenant_id.value,
            event_type,
            url,
        )
        return False
