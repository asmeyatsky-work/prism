"""
Gateway Domain — TenantConfig Entity

Architectural Intent:
- Stores per-tenant configuration for the PRISM platform
- Controls which bounded-context features are enabled for a brand
- Holds webhook subscriptions and PIM connector settings
- Frozen dataclass enforces immutability (skill2026 Rule 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import TenantId

from prism.gateway.domain.value_objects.api_types import ConnectorType


# Valid feature flags corresponding to PRISM bounded contexts
VALID_FEATURES: frozenset[str] = frozenset(
    {
        "CATALOGUE",
        "INTELLIGENCE",
        "DISCOVERY",
        "TRYON",
        "COMMERCE",
        "PAYMENT",
        "AGENTIC_CX",
    }
)


@dataclass(frozen=True)
class TenantConfig(Entity):
    """
    Per-tenant platform configuration.

    Fields:
        tenant_id: The tenant this configuration belongs to.
        brand_name: Display name for the luxury brand.
        enabled_features: Tuple of activated PRISM features.
        api_rate_limit: Global rate limit (requests/min) for this tenant.
        webhook_urls: Mapping of event_type -> delivery URL.
        pim_connector_type: Which PIM system is integrated.
        custom_settings: Arbitrary tenant-specific overrides.
    """

    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="UNSET"))
    brand_name: str = ""
    enabled_features: tuple[str, ...] = field(default=())
    api_rate_limit: int = 5000
    webhook_urls: dict[str, str] = field(default_factory=dict)
    pim_connector_type: ConnectorType = ConnectorType.CUSTOM
    custom_settings: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Validate that all enabled features are recognised
        invalid = set(self.enabled_features) - VALID_FEATURES
        if invalid:
            raise ValueError(
                f"Unknown features: {', '.join(sorted(invalid))}. "
                f"Valid features: {', '.join(sorted(VALID_FEATURES))}"
            )

    def has_feature(self, feature: str) -> bool:
        """Check whether a specific PRISM feature is enabled for this tenant."""
        return feature in self.enabled_features

    def get_webhook_url(self, event_type: str) -> str | None:
        """Return the webhook delivery URL for a given event type, or None."""
        return self.webhook_urls.get(event_type)
