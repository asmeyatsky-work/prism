"""
Gateway Domain — Port Interfaces (Protocols)

Architectural Intent:
- Protocol-based ports define contracts for infrastructure adapters
- Domain layer depends only on these abstractions, never on implementations
- Each port maps to exactly one infrastructure concern
- Per skill2026 Rule 4: ports live in domain, adapters in infrastructure
"""

from __future__ import annotations

from typing import Any, Protocol

from prism.shared.domain.value_objects import TenantId

from prism.gateway.domain.entities.api_key import APIKey
from prism.gateway.domain.entities.tenant_config import TenantConfig
from prism.gateway.domain.value_objects.api_types import ConnectorConfig, RateLimitConfig


class APIKeyRepositoryPort(Protocol):
    """Port for API key persistence and lookup."""

    async def validate_key(self, key_hash: str) -> APIKey | None:
        """Look up an API key by its hash. Returns None if not found."""
        ...

    async def get_by_tenant(self, tenant_id: TenantId) -> list[APIKey]:
        """Return all API keys belonging to a tenant."""
        ...


class TenantConfigPort(Protocol):
    """Port for tenant configuration persistence."""

    async def get_config(self, tenant_id: TenantId) -> TenantConfig:
        """Retrieve the configuration for a tenant. Raises if not found."""
        ...

    async def update_config(self, config: TenantConfig) -> None:
        """Persist an updated tenant configuration."""
        ...


class RateLimiterPort(Protocol):
    """Port for distributed rate limiting."""

    async def check_rate_limit(
        self, key_id: str, limit_config: RateLimitConfig
    ) -> bool:
        """Return True if the request is within rate limits, False if throttled."""
        ...

    async def record_request(self, key_id: str) -> None:
        """Record that a request was made against the given key."""
        ...


class WebhookDispatchPort(Protocol):
    """Port for delivering webhook events to tenant-registered endpoints."""

    async def dispatch(
        self, tenant_id: TenantId, event_type: str, payload: dict[str, Any]
    ) -> bool:
        """
        Dispatch a webhook event to the tenant's registered URL.

        Returns True if delivery was acknowledged, False on failure.
        """
        ...


class PIMConnectorPort(Protocol):
    """Port for synchronising product data from external PIM systems."""

    async def sync_products(
        self, config: ConnectorConfig, tenant_id: TenantId
    ) -> int:
        """
        Pull product data from the configured PIM system.

        Returns the number of products synchronised.
        """
        ...
