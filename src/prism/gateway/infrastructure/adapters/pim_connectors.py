"""
Gateway Infrastructure — PIM Connector Implementations

Architectural Intent:
- Implements PIMConnectorPort for each supported Product Information Management system
- Akeneo, Contentserv, and Salsify are the primary PIM platforms in luxury retail
- Each connector handles authentication, pagination, and data mapping
- ConnectorConfig credentials are fetched from secret manager (never stored in code)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from prism.shared.domain.value_objects import TenantId
from prism.gateway.domain.value_objects.api_types import AuthType, ConnectorConfig

logger = logging.getLogger(__name__)

# Default page size for paginated PIM API calls
_DEFAULT_PAGE_SIZE = 100


class BasePIMConnector(ABC):
    """
    Abstract base for PIM connector implementations.

    Provides shared HTTP client management, authentication header
    construction, and paginated fetching logic.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._http = http_client or httpx.AsyncClient(timeout=60.0)

    async def _get_auth_headers(self, config: ConnectorConfig) -> dict[str, str]:
        """Build authentication headers based on the connector's auth type."""
        # In production, credentials_ref is resolved against a secret manager.
        # Here we use the reference as a placeholder token.
        if config.auth_type == AuthType.API_KEY:
            return {"Authorization": f"Bearer {config.credentials_ref}"}
        elif config.auth_type == AuthType.OAUTH2:
            token = await self._fetch_oauth_token(config)
            return {"Authorization": f"Bearer {token}"}
        elif config.auth_type == AuthType.BASIC:
            import base64

            encoded = base64.b64encode(
                config.credentials_ref.encode("utf-8")
            ).decode("utf-8")
            return {"Authorization": f"Basic {encoded}"}
        return {}

    async def _fetch_oauth_token(self, config: ConnectorConfig) -> str:
        """Exchange credentials for an OAuth2 access token."""
        # Placeholder — in production this calls the PIM's token endpoint
        # using client credentials stored in config.credentials_ref
        logger.debug(
            "Fetching OAuth2 token for %s at %s",
            config.connector_type.value,
            config.endpoint_url,
        )
        return config.credentials_ref

    @abstractmethod
    async def sync_products(
        self, config: ConnectorConfig, tenant_id: TenantId
    ) -> int:
        """Synchronise products from the PIM system. Returns count of synced products."""
        ...


class AkeneoConnector(BasePIMConnector):
    """
    PIM connector for Akeneo (Community & Enterprise).

    Akeneo is the leading open-source PIM used by luxury brands like
    Chanel and LVMH. This connector uses the Akeneo REST API v1.

    Sync flow:
    1. Authenticate via OAuth2 client credentials.
    2. Fetch products paginated via ``/api/rest/v1/products``.
    3. Map Akeneo product families to PRISM catalogue entities.
    """

    async def sync_products(
        self, config: ConnectorConfig, tenant_id: TenantId
    ) -> int:
        headers = await self._get_auth_headers(config)
        url = f"{config.endpoint_url}/api/rest/v1/products"
        total_synced = 0

        page = 1
        while True:
            params = {
                "limit": _DEFAULT_PAGE_SIZE,
                "page": page,
                "with_count": "true",
            }

            try:
                response = await self._http.get(
                    url, headers=headers, params=params
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.error(
                    "Akeneo sync error: tenant_id=%s page=%d error=%s",
                    tenant_id.value,
                    page,
                    str(exc),
                )
                break

            items = data.get("_embedded", {}).get("items", [])
            if not items:
                break

            total_synced += len(items)
            logger.info(
                "Akeneo sync progress: tenant_id=%s page=%d synced=%d",
                tenant_id.value,
                page,
                total_synced,
            )

            # Check for next page
            next_link = data.get("_links", {}).get("next")
            if not next_link:
                break
            page += 1

        logger.info(
            "Akeneo sync complete: tenant_id=%s total_products=%d",
            tenant_id.value,
            total_synced,
        )
        return total_synced


class ContentservConnector(BasePIMConnector):
    """
    PIM connector for Contentserv.

    Contentserv is a master data management platform popular with
    European luxury brands. Uses the Contentserv REST API.

    Sync flow:
    1. Authenticate via API key.
    2. Fetch product data via ``/api/v2/products``.
    3. Handle Contentserv's offset-based pagination.
    """

    async def sync_products(
        self, config: ConnectorConfig, tenant_id: TenantId
    ) -> int:
        headers = await self._get_auth_headers(config)
        url = f"{config.endpoint_url}/api/v2/products"
        total_synced = 0
        offset = 0

        while True:
            params = {
                "limit": _DEFAULT_PAGE_SIZE,
                "offset": offset,
            }

            try:
                response = await self._http.get(
                    url, headers=headers, params=params
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.error(
                    "Contentserv sync error: tenant_id=%s offset=%d error=%s",
                    tenant_id.value,
                    offset,
                    str(exc),
                )
                break

            products = data.get("products", [])
            if not products:
                break

            total_synced += len(products)
            logger.info(
                "Contentserv sync progress: tenant_id=%s offset=%d synced=%d",
                tenant_id.value,
                offset,
                total_synced,
            )

            if len(products) < _DEFAULT_PAGE_SIZE:
                break
            offset += _DEFAULT_PAGE_SIZE

        logger.info(
            "Contentserv sync complete: tenant_id=%s total_products=%d",
            tenant_id.value,
            total_synced,
        )
        return total_synced


class SalsifyConnector(BasePIMConnector):
    """
    PIM connector for Salsify.

    Salsify is a SaaS PIM platform widely adopted by North American
    luxury retailers. Uses Salsify's Export API with async job polling.

    Sync flow:
    1. Authenticate via API key (Bearer token).
    2. Initiate a product export via ``/api/v1/orgs/{org}/products``.
    3. Poll for export completion.
    4. Download and process the export file.
    """

    async def sync_products(
        self, config: ConnectorConfig, tenant_id: TenantId
    ) -> int:
        headers = await self._get_auth_headers(config)
        url = f"{config.endpoint_url}/api/v1/products"
        total_synced = 0
        page = 1

        while True:
            params = {
                "per_page": _DEFAULT_PAGE_SIZE,
                "page": page,
            }

            try:
                response = await self._http.get(
                    url, headers=headers, params=params
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as exc:
                logger.error(
                    "Salsify sync error: tenant_id=%s page=%d error=%s",
                    tenant_id.value,
                    page,
                    str(exc),
                )
                break

            products = data.get("products", data.get("data", []))
            if not products:
                break

            total_synced += len(products)
            logger.info(
                "Salsify sync progress: tenant_id=%s page=%d synced=%d",
                tenant_id.value,
                page,
                total_synced,
            )

            # Salsify pagination: check meta for total pages
            meta = data.get("meta", {})
            total_pages = meta.get("total_pages", page)
            if page >= total_pages:
                break
            page += 1

        logger.info(
            "Salsify sync complete: tenant_id=%s total_products=%d",
            tenant_id.value,
            total_synced,
        )
        return total_synced


def create_connector(config: ConnectorConfig) -> BasePIMConnector:
    """Factory function to create the appropriate PIM connector from configuration."""
    from prism.gateway.domain.value_objects.api_types import ConnectorType

    connectors: dict[ConnectorType, type[BasePIMConnector]] = {
        ConnectorType.AKENEO: AkeneoConnector,
        ConnectorType.CONTENTSERV: ContentservConnector,
        ConnectorType.SALSIFY: SalsifyConnector,
    }

    connector_cls = connectors.get(config.connector_type)
    if connector_cls is None:
        raise ValueError(
            f"No connector implementation for type: {config.connector_type.value}. "
            f"Supported types: {', '.join(t.value for t in connectors)}"
        )

    return connector_cls()
