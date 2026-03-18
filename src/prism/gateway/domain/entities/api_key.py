"""
Gateway Domain — APIKey Entity

Architectural Intent:
- Represents an API key issued to a tenant for authenticating PRISM API requests
- The raw key is NEVER stored; only the SHA-256 hash is persisted
- Scopes control which bounded-context operations the key authorises
- Frozen dataclass enforces immutability (skill2026 Rule 3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from prism.shared.domain.entities import Entity
from prism.shared.domain.value_objects import TenantId

from prism.gateway.domain.value_objects.api_types import APIScope


@dataclass(frozen=True)
class APIKey(Entity):
    """
    API key entity for tenant authentication and authorisation.

    Fields:
        key_id: Unique identifier for this API key (aliases Entity.id).
        tenant_id: Owning tenant — all requests are scoped to this tenant.
        key_hash: SHA-256 hash of the raw API key; raw value is never stored.
        name: Human-readable label (e.g. "Production iOS App").
        scopes: Tuple of granted permission scopes.
        rate_limit_per_minute: Per-key request ceiling (overrides tenant default).
        enabled: Administrative toggle — disabled keys are immediately rejected.
        expires_at: Optional expiry; None means the key does not expire.
    """

    key_id: str = ""
    tenant_id: TenantId = field(default_factory=lambda: TenantId(value="UNSET"))
    key_hash: str = ""
    name: str = ""
    scopes: tuple[str, ...] = field(default=())
    rate_limit_per_minute: int = 1000
    enabled: bool = True
    expires_at: datetime | None = None

    def is_valid(self) -> bool:
        """Check whether this key is currently usable for authentication."""
        if not self.enabled:
            return False
        if self.is_expired():
            return False
        if not self.key_hash:
            return False
        return True

    def has_scope(self, scope: str | APIScope) -> bool:
        """Return True if this key grants the requested scope."""
        scope_value = scope.value if isinstance(scope, APIScope) else scope
        # ADMIN scope grants access to everything
        if APIScope.ADMIN.value in self.scopes:
            return True
        return scope_value in self.scopes

    def is_expired(self) -> bool:
        """Return True if this key has passed its expiration timestamp."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at
