"""
Gateway Infrastructure — Apigee API Management Adapter

Architectural Intent:
- Integrates with Google Apigee for API lifecycle management
- Handles API proxy deployment, developer app provisioning, and analytics
- Used in GCP-hosted production environments for enterprise API governance
- Wraps the Apigee Management API v1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApigeeConfig:
    """Connection configuration for the Apigee Management API."""

    organization: str
    environment: str
    base_url: str = "https://apigee.googleapis.com/v1"
    project_id: str = ""
    credentials_ref: str = ""


class ApigeeAdapter:
    """
    Adapter for Google Apigee API management platform.

    Provides operations for:
    - API proxy deployment and versioning
    - Developer and developer app management
    - API product configuration
    - Analytics and quota management

    All calls are authenticated via GCP service account credentials.
    """

    def __init__(self, config: ApigeeConfig, http_client: httpx.AsyncClient | None = None) -> None:
        self._config = config
        self._http = http_client or httpx.AsyncClient(timeout=30.0)

    @property
    def _org_url(self) -> str:
        return f"{self._config.base_url}/organizations/{self._config.organization}"

    async def deploy_api_proxy(
        self, proxy_name: str, revision: int
    ) -> dict[str, Any]:
        """Deploy a specific revision of an API proxy to the configured environment."""
        url = (
            f"{self._org_url}/environments/{self._config.environment}"
            f"/apis/{proxy_name}/revisions/{revision}/deployments"
        )
        response = await self._http.post(url)
        response.raise_for_status()
        logger.info(
            "Deployed proxy %s revision %d to %s",
            proxy_name,
            revision,
            self._config.environment,
        )
        return response.json()

    async def create_api_product(
        self,
        name: str,
        display_name: str,
        proxies: list[str],
        scopes: list[str],
        quota: int = 1000,
        quota_interval: int = 1,
        quota_time_unit: str = "minute",
    ) -> dict[str, Any]:
        """Create an API product that bundles proxies with quota settings."""
        url = f"{self._org_url}/apiproducts"
        payload = {
            "name": name,
            "displayName": display_name,
            "proxies": proxies,
            "scopes": scopes,
            "quota": str(quota),
            "quotaInterval": str(quota_interval),
            "quotaTimeUnit": quota_time_unit,
            "attributes": [
                {"name": "access", "value": "public"},
            ],
        }
        response = await self._http.post(url, json=payload)
        response.raise_for_status()
        logger.info("Created API product: %s", name)
        return response.json()

    async def register_developer(
        self, email: str, first_name: str, last_name: str
    ) -> dict[str, Any]:
        """Register a developer (tenant representative) in Apigee."""
        url = f"{self._org_url}/developers"
        payload = {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "userName": email.split("@")[0],
        }
        response = await self._http.post(url, json=payload)
        response.raise_for_status()
        logger.info("Registered developer: %s", email)
        return response.json()

    async def create_developer_app(
        self,
        developer_email: str,
        app_name: str,
        api_products: list[str],
    ) -> dict[str, Any]:
        """Create a developer app bound to API products, returning consumer credentials."""
        url = f"{self._org_url}/developers/{developer_email}/apps"
        payload = {
            "name": app_name,
            "apiProducts": api_products,
        }
        response = await self._http.post(url, json=payload)
        response.raise_for_status()
        logger.info(
            "Created developer app %s for %s", app_name, developer_email
        )
        return response.json()

    async def get_api_analytics(
        self,
        dimension: str = "apis",
        metric: str = "sum(message_count)",
        time_range: str = "last24hours",
    ) -> dict[str, Any]:
        """Retrieve analytics data from Apigee."""
        url = (
            f"{self._org_url}/environments/{self._config.environment}/stats/{dimension}"
        )
        params = {
            "select": metric,
            "timeRange": time_range,
        }
        response = await self._http.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Verify connectivity to the Apigee Management API."""
        try:
            url = f"{self._org_url}/environments/{self._config.environment}"
            response = await self._http.get(url)
            return response.status_code == 200
        except Exception:
            logger.exception("Apigee health check failed")
            return False
