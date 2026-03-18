"""
Gateway Domain — Value Objects for API types, rate limiting, webhooks, and connectors.

Architectural Intent:
- Immutable value objects defining the vocabulary of the Gateway bounded context
- APIScope enumerates all permission scopes across PRISM bounded contexts
- RateLimitConfig, WebhookConfig, ConnectorConfig are configuration value objects
- ConnectorType captures supported PIM integrations for luxury retail
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from prism.shared.domain.value_objects import ValueObject


class APIScope(str, Enum):
    """Permission scopes for API key authorisation across PRISM services."""

    CATALOGUE_READ = "catalogue:read"
    CATALOGUE_WRITE = "catalogue:write"
    SEARCH = "discovery:search"
    TRYON = "tryon:execute"
    PAYMENT = "payment:process"
    AGENT = "agentic_cx:invoke"
    ADMIN = "admin:full"


class ConnectorType(str, Enum):
    """Supported PIM connector types for luxury retail product data ingestion."""

    AKENEO = "AKENEO"
    CONTENTSERV = "CONTENTSERV"
    SALSIFY = "SALSIFY"
    CUSTOM = "CUSTOM"


class AuthType(str, Enum):
    """Authentication mechanisms for external connector integrations."""

    API_KEY = "API_KEY"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"


@dataclass(frozen=True)
class RateLimitConfig(ValueObject):
    """
    Rate limiting configuration for API access control.

    Uses a sliding-window algorithm: up to ``requests_per_minute`` requests
    are permitted within a rolling ``window_seconds`` window, with short
    bursts up to ``burst_size`` allowed.
    """

    requests_per_minute: int
    burst_size: int
    window_seconds: int = 60

    def __post_init__(self) -> None:
        if self.requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        if self.burst_size <= 0:
            raise ValueError("burst_size must be positive")
        if self.window_seconds <= 0:
            raise ValueError("window_seconds must be positive")


@dataclass(frozen=True)
class WebhookConfig(ValueObject):
    """
    Webhook delivery configuration for a tenant event subscription.

    The ``secret`` is used for HMAC-SHA256 signature verification on the
    receiving end. Retries use exponential back-off up to ``retry_count``.
    """

    url: str
    events: tuple[str, ...]
    secret: str
    retry_count: int = 3

    def __post_init__(self) -> None:
        if not self.url:
            raise ValueError("Webhook URL cannot be empty")
        if not self.events:
            raise ValueError("Webhook must subscribe to at least one event")
        if not self.secret:
            raise ValueError("Webhook secret cannot be empty")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")


@dataclass(frozen=True)
class ConnectorConfig(ValueObject):
    """
    PIM connector configuration for product data synchronisation.

    ``credentials_ref`` is a reference to the secret manager entry — raw
    credentials are never stored in domain objects.
    """

    connector_type: ConnectorType
    endpoint_url: str
    auth_type: AuthType
    credentials_ref: str

    def __post_init__(self) -> None:
        if not self.endpoint_url:
            raise ValueError("Connector endpoint URL cannot be empty")
        if not self.credentials_ref:
            raise ValueError("credentials_ref cannot be empty")
