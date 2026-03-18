"""
Gateway Context — Mock API Key, Tenant Config, Rate Limiter, Webhook, and PIM Adapters

Provides mock implementations of:
- APIKeyRepositoryPort   -> MockAPIKeyRepository
- TenantConfigPort       -> MockTenantConfig
- RateLimiterPort        -> MockRateLimiter
- WebhookDispatchPort    -> MockWebhookDispatch
- PIMConnectorPort       -> MockPIMConnector

MockAPIKeyRepository accepts "demo-api-key" with all scopes.
MockTenantConfig returns pre-built configurations for "gucci" and "lvmh" tenants.
MockRateLimiter always allows requests (no throttling in demo mode).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from prism.gateway.domain.entities.api_key import APIKey
from prism.gateway.domain.entities.tenant_config import TenantConfig
from prism.gateway.domain.value_objects.api_types import (
    APIScope,
    ConnectorConfig,
    ConnectorType,
    RateLimitConfig,
)
from prism.shared.domain.value_objects import TenantId

logger = logging.getLogger("prism.demo.gateway")

# ── Demo API key configuration ──────────────────────────────────────────

_DEMO_KEY_RAW = "demo-api-key"
_DEMO_KEY_HASH = hashlib.sha256(_DEMO_KEY_RAW.encode()).hexdigest()

_ALL_SCOPES = tuple(scope.value for scope in APIScope)

_DEMO_API_KEYS: dict[str, APIKey] = {
    _DEMO_KEY_HASH: APIKey(
        key_id="key_demo_001",
        tenant_id=TenantId(value="gucci"),
        key_hash=_DEMO_KEY_HASH,
        name="Demo All-Access Key",
        scopes=_ALL_SCOPES,
        rate_limit_per_minute=10000,
        enabled=True,
        expires_at=None,
    ),
}

# Secondary keys for multi-tenant testing
_LVMH_KEY_RAW = "lvmh-demo-key"
_LVMH_KEY_HASH = hashlib.sha256(_LVMH_KEY_RAW.encode()).hexdigest()

_DEMO_API_KEYS[_LVMH_KEY_HASH] = APIKey(
    key_id="key_demo_002",
    tenant_id=TenantId(value="lvmh"),
    key_hash=_LVMH_KEY_HASH,
    name="LVMH Demo Key",
    scopes=_ALL_SCOPES,
    rate_limit_per_minute=10000,
    enabled=True,
    expires_at=None,
)


class MockAPIKeyRepository:
    """
    In-memory API key repository pre-seeded with demo keys.
    Accepts "demo-api-key" (Gucci tenant, all scopes) and
    "lvmh-demo-key" (LVMH tenant, all scopes).
    """

    def __init__(self) -> None:
        self._keys: dict[str, APIKey] = dict(_DEMO_API_KEYS)
        # Index by tenant
        self._by_tenant: dict[str, list[APIKey]] = {}
        for key in self._keys.values():
            tid = key.tenant_id.value
            if tid not in self._by_tenant:
                self._by_tenant[tid] = []
            self._by_tenant[tid].append(key)

    async def validate_key(self, key_hash: str) -> APIKey | None:
        api_key = self._keys.get(key_hash)
        if api_key and api_key.is_valid():
            return api_key
        return None

    async def get_by_tenant(self, tenant_id: TenantId) -> list[APIKey]:
        return list(self._by_tenant.get(tenant_id.value, []))


# ── Tenant configurations ───────────────────────────────────────────────

_DEMO_TENANT_CONFIGS: dict[str, TenantConfig] = {
    "gucci": TenantConfig(
        tenant_id=TenantId(value="gucci"),
        brand_name="Gucci",
        enabled_features=(
            "CATALOGUE",
            "INTELLIGENCE",
            "DISCOVERY",
            "TRYON",
            "COMMERCE",
            "PAYMENT",
            "AGENTIC_CX",
        ),
        api_rate_limit=10000,
        webhook_urls={
            "product.enriched": "https://hooks.gucci.example/prism/enriched",
            "payment.captured": "https://hooks.gucci.example/prism/payment",
            "conversation.escalated": "https://hooks.gucci.example/prism/escalation",
        },
        pim_connector_type=ConnectorType.AKENEO,
        custom_settings={
            "brand_tone": "sophisticated, understated luxury, Italian heritage emphasis",
            "default_currency": "EUR",
            "primary_markets": ["IT", "FR", "US", "GB", "JP", "CN"],
            "tryon_background": "studio_white",
            "ai_model_preference": "gemini-2.0-flash",
        },
    ),
    "lvmh": TenantConfig(
        tenant_id=TenantId(value="lvmh"),
        brand_name="LVMH Group",
        enabled_features=(
            "CATALOGUE",
            "INTELLIGENCE",
            "DISCOVERY",
            "COMMERCE",
            "PAYMENT",
            "AGENTIC_CX",
        ),
        api_rate_limit=15000,
        webhook_urls={
            "product.enriched": "https://hooks.lvmh.example/prism/enriched",
            "payment.captured": "https://hooks.lvmh.example/prism/payment",
        },
        pim_connector_type=ConnectorType.CONTENTSERV,
        custom_settings={
            "brand_tone": "timeless French elegance, artisanal savoir-faire",
            "default_currency": "EUR",
            "primary_markets": ["FR", "US", "JP", "CN", "KR", "AE"],
            "multi_brand": True,
            "sub_brands": ["Louis Vuitton", "Dior", "Fendi", "Givenchy", "Celine"],
        },
    ),
}


class MockTenantConfig:
    """
    In-memory tenant configuration store pre-seeded with "gucci" and "lvmh"
    tenant configurations. Both tenants have all PRISM features enabled.
    """

    def __init__(self) -> None:
        self._configs: dict[str, TenantConfig] = dict(_DEMO_TENANT_CONFIGS)

    async def get_config(self, tenant_id: TenantId) -> TenantConfig:
        config = self._configs.get(tenant_id.value)
        if config is None:
            raise KeyError(
                f"Tenant '{tenant_id.value}' not found. "
                f"Available tenants: {', '.join(self._configs.keys())}"
            )
        return config

    async def update_config(self, config: TenantConfig) -> None:
        self._configs[config.tenant_id.value] = config
        logger.info("Tenant config updated: %s", config.tenant_id.value)


class MockRateLimiter:
    """
    Mock rate limiter that always allows requests.
    Records request counts for observability but never throttles.
    """

    def __init__(self) -> None:
        self._request_counts: dict[str, int] = {}

    async def check_rate_limit(
        self,
        key_id: str,
        limit_config: RateLimitConfig,
    ) -> bool:
        # Always allow in demo mode
        return True

    async def record_request(self, key_id: str) -> None:
        self._request_counts[key_id] = self._request_counts.get(key_id, 0) + 1

    @property
    def request_counts(self) -> dict[str, int]:
        """Access request counts for monitoring."""
        return dict(self._request_counts)


class MockWebhookDispatch:
    """
    Mock webhook dispatcher that logs all dispatched events.
    Always returns True (successful delivery).
    """

    def __init__(self) -> None:
        self._dispatch_log: list[dict[str, Any]] = []

    async def dispatch(
        self,
        tenant_id: TenantId,
        event_type: str,
        payload: dict[str, Any],
    ) -> bool:
        entry = {
            "tenant_id": tenant_id.value,
            "event_type": event_type,
            "payload": payload,
        }
        self._dispatch_log.append(entry)
        logger.info(
            "Webhook dispatched: %s/%s (%d bytes)",
            tenant_id.value,
            event_type,
            len(str(payload)),
        )
        return True

    @property
    def dispatch_log(self) -> list[dict[str, Any]]:
        """Access the complete dispatch log for testing/inspection."""
        return list(self._dispatch_log)


class MockPIMConnector:
    """
    Mock PIM connector that performs no actual synchronisation.
    Returns 0 products synced. Logs the sync attempt for visibility.
    """

    async def sync_products(
        self,
        config: ConnectorConfig,
        tenant_id: TenantId,
    ) -> int:
        logger.info(
            "PIM sync requested: %s connector for tenant %s (no-op in demo mode)",
            config.connector_type.value,
            tenant_id.value,
        )
        return 0
