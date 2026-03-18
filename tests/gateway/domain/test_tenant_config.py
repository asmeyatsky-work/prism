"""
Tests for Gateway Domain — TenantConfig Entity

Covers:
- Feature flag validation and lookup
- Webhook URL retrieval
- Invalid feature rejection
- Immutability enforcement
"""

from __future__ import annotations

import pytest

from prism.shared.domain.value_objects import TenantId
from prism.gateway.domain.entities.tenant_config import (
    VALID_FEATURES,
    TenantConfig,
)
from prism.gateway.domain.value_objects.api_types import ConnectorType


@pytest.fixture
def tenant_id() -> TenantId:
    return TenantId(value="tenant-hermes")


@pytest.fixture
def full_config(tenant_id: TenantId) -> TenantConfig:
    return TenantConfig(
        tenant_id=tenant_id,
        brand_name="Hermes",
        enabled_features=("CATALOGUE", "INTELLIGENCE", "DISCOVERY", "COMMERCE"),
        api_rate_limit=10000,
        webhook_urls={
            "order.created": "https://hermes.example.com/webhooks/orders",
            "product.updated": "https://hermes.example.com/webhooks/products",
        },
        pim_connector_type=ConnectorType.AKENEO,
        custom_settings={"theme": "orange", "region": "EMEA"},
    )


class TestTenantConfigFeatures:
    """Tests for feature flag management."""

    def test_has_enabled_feature(self, full_config: TenantConfig) -> None:
        assert full_config.has_feature("CATALOGUE") is True
        assert full_config.has_feature("INTELLIGENCE") is True
        assert full_config.has_feature("DISCOVERY") is True
        assert full_config.has_feature("COMMERCE") is True

    def test_missing_feature_returns_false(self, full_config: TenantConfig) -> None:
        assert full_config.has_feature("TRYON") is False
        assert full_config.has_feature("PAYMENT") is False
        assert full_config.has_feature("AGENTIC_CX") is False

    def test_invalid_feature_raises_on_creation(
        self, tenant_id: TenantId
    ) -> None:
        with pytest.raises(ValueError, match="Unknown features"):
            TenantConfig(
                tenant_id=tenant_id,
                brand_name="BadConfig",
                enabled_features=("CATALOGUE", "INVALID_FEATURE"),
            )

    def test_all_valid_features_accepted(self, tenant_id: TenantId) -> None:
        config = TenantConfig(
            tenant_id=tenant_id,
            brand_name="AllFeatures",
            enabled_features=tuple(sorted(VALID_FEATURES)),
        )
        for feature in VALID_FEATURES:
            assert config.has_feature(feature) is True

    def test_empty_features_is_valid(self, tenant_id: TenantId) -> None:
        config = TenantConfig(
            tenant_id=tenant_id,
            brand_name="NoFeatures",
            enabled_features=(),
        )
        assert config.has_feature("CATALOGUE") is False


class TestTenantConfigWebhooks:
    """Tests for webhook URL management."""

    def test_get_registered_webhook_url(self, full_config: TenantConfig) -> None:
        url = full_config.get_webhook_url("order.created")
        assert url == "https://hermes.example.com/webhooks/orders"

    def test_get_unregistered_webhook_returns_none(
        self, full_config: TenantConfig
    ) -> None:
        assert full_config.get_webhook_url("payment.failed") is None

    def test_empty_webhook_urls(self, tenant_id: TenantId) -> None:
        config = TenantConfig(
            tenant_id=tenant_id,
            brand_name="NoWebhooks",
        )
        assert config.get_webhook_url("order.created") is None


class TestTenantConfigConnector:
    """Tests for PIM connector configuration."""

    def test_default_connector_is_custom(self, tenant_id: TenantId) -> None:
        config = TenantConfig(
            tenant_id=tenant_id,
            brand_name="Default",
        )
        assert config.pim_connector_type == ConnectorType.CUSTOM

    def test_akeneo_connector(self, full_config: TenantConfig) -> None:
        assert full_config.pim_connector_type == ConnectorType.AKENEO

    def test_all_connector_types(self, tenant_id: TenantId) -> None:
        for ct in ConnectorType:
            config = TenantConfig(
                tenant_id=tenant_id,
                brand_name="TestBrand",
                pim_connector_type=ct,
            )
            assert config.pim_connector_type == ct


class TestTenantConfigImmutability:
    """Verify that TenantConfig is a frozen dataclass."""

    def test_cannot_mutate_brand_name(self, full_config: TenantConfig) -> None:
        with pytest.raises(AttributeError):
            full_config.brand_name = "Modified"  # type: ignore[misc]

    def test_cannot_mutate_rate_limit(self, full_config: TenantConfig) -> None:
        with pytest.raises(AttributeError):
            full_config.api_rate_limit = 999  # type: ignore[misc]

    def test_cannot_mutate_features(self, full_config: TenantConfig) -> None:
        with pytest.raises(AttributeError):
            full_config.enabled_features = ("TRYON",)  # type: ignore[misc]


class TestTenantConfigDefaults:
    """Test default values."""

    def test_default_rate_limit(self, tenant_id: TenantId) -> None:
        config = TenantConfig(tenant_id=tenant_id, brand_name="Defaults")
        assert config.api_rate_limit == 5000

    def test_default_custom_settings_empty(self, tenant_id: TenantId) -> None:
        config = TenantConfig(tenant_id=tenant_id, brand_name="Defaults")
        assert config.custom_settings == {}
