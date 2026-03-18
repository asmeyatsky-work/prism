"""
Gateway Application — Data Transfer Objects

Architectural Intent:
- Pydantic models for API request/response serialisation
- DTOs decouple domain entities from external representation
- Used by presentation layer and inter-context communication
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ServiceStatus(str, Enum):
    """Health status for individual services."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class APIKeyDTO(BaseModel):
    """API key representation for external consumers (never exposes the hash)."""

    key_id: str
    tenant_id: str
    name: str
    scopes: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 1000
    enabled: bool = True
    created_at: datetime | None = None
    expires_at: datetime | None = None


class TenantConfigDTO(BaseModel):
    """Tenant configuration representation for API responses."""

    tenant_id: str
    brand_name: str
    enabled_features: list[str] = Field(default_factory=list)
    api_rate_limit: int = 5000
    webhook_urls: dict[str, str] = Field(default_factory=dict)
    pim_connector_type: str = "CUSTOM"
    custom_settings: dict[str, object] = Field(default_factory=dict)


class WebhookEventDTO(BaseModel):
    """Webhook event payload for outbound delivery."""

    event_id: str
    event_type: str
    tenant_id: str
    occurred_at: datetime
    payload: dict[str, object] = Field(default_factory=dict)
    delivery_url: str = ""
    attempt: int = 1
    max_retries: int = 3


class ServiceHealthDTO(BaseModel):
    """Health status of an individual bounded-context service."""

    name: str
    status: ServiceStatus = ServiceStatus.HEALTHY
    latency_ms: float = 0.0
    message: str = ""


class HealthCheckDTO(BaseModel):
    """Aggregate health check response for the entire PRISM platform."""

    status: ServiceStatus = ServiceStatus.HEALTHY
    version: str = "1.0.0"
    timestamp: datetime | None = None
    services: list[ServiceHealthDTO] = Field(default_factory=list)
    uptime_seconds: float = 0.0

    @property
    def is_healthy(self) -> bool:
        """Return True if all services report healthy status."""
        return all(s.status == ServiceStatus.HEALTHY for s in self.services)

    @property
    def degraded_services(self) -> list[str]:
        """Return names of services that are not fully healthy."""
        return [
            s.name
            for s in self.services
            if s.status != ServiceStatus.HEALTHY
        ]
