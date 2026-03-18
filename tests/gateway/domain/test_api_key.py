"""
Tests for Gateway Domain — APIKey Entity

Covers:
- Key validity checks (enabled, expired, missing hash)
- Scope authorisation including ADMIN wildcard
- Expiration boundary conditions
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from prism.shared.domain.value_objects import TenantId
from prism.gateway.domain.entities.api_key import APIKey
from prism.gateway.domain.value_objects.api_types import APIScope


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId(value="tenant-gucci")


@pytest.fixture
def valid_key(tenant_id: TenantId) -> APIKey:
    return APIKey(
        key_id="key-001",
        tenant_id=tenant_id,
        key_hash="abc123hash",
        name="Production iOS App",
        scopes=(APIScope.CATALOGUE_READ.value, APIScope.SEARCH.value),
        rate_limit_per_minute=500,
        enabled=True,
        expires_at=datetime.now(UTC) + timedelta(days=365),
    )


class TestAPIKeyValidity:
    """Tests for APIKey.is_valid()."""

    def test_valid_key_returns_true(self, valid_key: APIKey) -> None:
        assert valid_key.is_valid() is True

    def test_disabled_key_is_invalid(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-disabled",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="Disabled Key",
            enabled=False,
        )
        assert key.is_valid() is False

    def test_expired_key_is_invalid(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-expired",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="Expired Key",
            enabled=True,
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert key.is_valid() is False

    def test_key_without_hash_is_invalid(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-nohash",
            tenant_id=tenant_id,
            key_hash="",
            name="No Hash Key",
            enabled=True,
        )
        assert key.is_valid() is False

    def test_key_without_expiry_is_valid(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-noexpiry",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="No Expiry Key",
            enabled=True,
            expires_at=None,
        )
        assert key.is_valid() is True


class TestAPIKeyExpiration:
    """Tests for APIKey.is_expired()."""

    def test_not_expired_when_future(self, valid_key: APIKey) -> None:
        assert valid_key.is_expired() is False

    def test_expired_when_past(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-past",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="Past Key",
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        assert key.is_expired() is True

    def test_not_expired_when_none(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-none-expiry",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="No Expiry",
            expires_at=None,
        )
        assert key.is_expired() is False


class TestAPIKeyScopes:
    """Tests for APIKey.has_scope()."""

    def test_has_granted_scope(self, valid_key: APIKey) -> None:
        assert valid_key.has_scope(APIScope.CATALOGUE_READ) is True
        assert valid_key.has_scope(APIScope.SEARCH) is True

    def test_missing_scope_returns_false(self, valid_key: APIKey) -> None:
        assert valid_key.has_scope(APIScope.PAYMENT) is False
        assert valid_key.has_scope(APIScope.ADMIN) is False

    def test_admin_scope_grants_all(self, tenant_id: TenantId) -> None:
        admin_key = APIKey(
            key_id="key-admin",
            tenant_id=tenant_id,
            key_hash="adminhash",
            name="Admin Key",
            scopes=(APIScope.ADMIN.value,),
        )
        assert admin_key.has_scope(APIScope.CATALOGUE_READ) is True
        assert admin_key.has_scope(APIScope.PAYMENT) is True
        assert admin_key.has_scope(APIScope.AGENT) is True
        assert admin_key.has_scope(APIScope.ADMIN) is True

    def test_has_scope_with_string(self, valid_key: APIKey) -> None:
        assert valid_key.has_scope("catalogue:read") is True
        assert valid_key.has_scope("payment:process") is False

    def test_empty_scopes(self, tenant_id: TenantId) -> None:
        key = APIKey(
            key_id="key-noscopes",
            tenant_id=tenant_id,
            key_hash="somehash",
            name="No Scopes",
            scopes=(),
        )
        assert key.has_scope(APIScope.CATALOGUE_READ) is False


class TestAPIKeyImmutability:
    """Verify that APIKey is a frozen dataclass."""

    def test_cannot_mutate_fields(self, valid_key: APIKey) -> None:
        with pytest.raises(AttributeError):
            valid_key.enabled = False  # type: ignore[misc]

    def test_cannot_mutate_name(self, valid_key: APIKey) -> None:
        with pytest.raises(AttributeError):
            valid_key.name = "Modified"  # type: ignore[misc]
