"""Gateway domain ports — protocol-based interfaces for infrastructure."""

from prism.gateway.domain.ports.gateway_ports import (
    APIKeyRepositoryPort,
    PIMConnectorPort,
    RateLimiterPort,
    TenantConfigPort,
    WebhookDispatchPort,
)

__all__ = [
    "APIKeyRepositoryPort",
    "PIMConnectorPort",
    "RateLimiterPort",
    "TenantConfigPort",
    "WebhookDispatchPort",
]
