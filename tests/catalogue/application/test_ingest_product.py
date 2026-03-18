"""
Ingest Product Use Case — Application Layer Tests

Tests the IngestProductUseCase with mocked infrastructure ports.
Verifies the full ingest workflow: validation, aggregate creation,
quality scoring, persistence, and event publishing.

Design Notes:
- Uses protocol-compatible mock implementations (not unittest.mock)
  to ensure type safety and catch interface drift
- Tests cover happy path, duplicate SKU rejection, and invalid currency
"""

from __future__ import annotations

import pytest

from prism.catalogue.application.commands.ingest_product import (
    IngestProductCommand,
    IngestProductUseCase,
)
from prism.catalogue.domain.entities.product import EnrichmentStatus, Product
from prism.catalogue.domain.events.catalogue_events import ProductIngestedEvent
from prism.shared.domain.events import DomainEvent, EventHandler
from prism.shared.domain.value_objects import TenantId


# ── Mock Implementations ─────────────────────────────────────────────


class InMemoryProductRepository:
    """
    In-memory implementation of ProductRepositoryPort for testing.

    Stores products in a dict keyed by (tenant_id, id).
    Provides all repository operations without infrastructure dependencies.
    """

    def __init__(self) -> None:
        self._products: dict[tuple[str, str], Product] = {}

    async def get_by_id(
        self, product_id: str, tenant_id: TenantId
    ) -> Product | None:
        return self._products.get((tenant_id.value, product_id))

    async def get_by_sku(
        self, sku: str, tenant_id: TenantId
    ) -> Product | None:
        for (tid, _), product in self._products.items():
            if tid == tenant_id.value and product.sku == sku:
                return product
        return None

    async def save(self, product: Product) -> None:
        key = (product.tenant_id.value, product.id)
        self._products[key] = product

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        matching = [
            p
            for (tid, _), p in self._products.items()
            if tid == tenant_id.value
        ]
        total = len(matching)
        return matching[offset : offset + limit], total

    async def search(
        self,
        tenant_id: TenantId,
        query: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        matching = [
            p
            for (tid, _), p in self._products.items()
            if tid == tenant_id.value
            and (
                query.lower() in p.name.lower()
                or query.lower() in p.description.lower()
            )
        ]
        total = len(matching)
        return matching[offset : offset + limit], total


class InMemoryEventBus:
    """In-memory event bus for testing — captures published events."""

    def __init__(self) -> None:
        self.published_events: list[DomainEvent] = []

    async def publish(self, events: list[DomainEvent]) -> None:
        self.published_events.extend(events)

    async def subscribe(
        self, event_type: type[DomainEvent], handler: EventHandler
    ) -> None:
        pass  # Not needed for these tests


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def product_repo() -> InMemoryProductRepository:
    """Fresh in-memory product repository."""
    return InMemoryProductRepository()


@pytest.fixture
def event_bus() -> InMemoryEventBus:
    """Fresh in-memory event bus."""
    return InMemoryEventBus()


@pytest.fixture
def use_case(
    product_repo: InMemoryProductRepository, event_bus: InMemoryEventBus
) -> IngestProductUseCase:
    """Configured IngestProductUseCase with test dependencies."""
    return IngestProductUseCase(
        product_repository=product_repo,
        event_bus=event_bus,
    )


@pytest.fixture
def valid_command() -> IngestProductCommand:
    """A valid ingest product command for a luxury dress."""
    return IngestProductCommand(
        tenant_id="tenant-luxe-001",
        sku="DRESS-EVE-001",
        name="Midnight Silk Evening Dress",
        brand="Maison Lumiere",
        description="An exquisite evening dress crafted from pure silk with hand-finished detailing.",
        category="Clothing",
        subcategory="Dresses",
        attributes={"material": "silk", "colour": "midnight blue"},
        image_uris=["gs://prism-assets/products/dress-001/front.jpg"],
        price_amount=2450.00,
        price_currency="EUR",
        taxonomy_codes=["LUX.RTW.DRESS.EVENING"],
        source="ucp",
    )


# ── Happy Path Tests ─────────────────────────────────────────────────


class TestIngestProductHappyPath:
    """Tests for successful product ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_creates_product(
        self,
        use_case: IngestProductUseCase,
        product_repo: InMemoryProductRepository,
        valid_command: IngestProductCommand,
    ) -> None:
        """Successful ingestion should create and persist a product."""
        result = await use_case.execute(valid_command)

        assert result.success is True
        assert result.value is not None
        assert result.value.sku == "DRESS-EVE-001"
        assert result.value.name == "Midnight Silk Evening Dress"
        assert result.value.brand == "Maison Lumiere"
        assert result.value.enrichment_status == "RAW"

        # Verify persisted
        tenant_id = TenantId(value="tenant-luxe-001")
        stored = await product_repo.get_by_sku("DRESS-EVE-001", tenant_id)
        assert stored is not None
        assert stored.sku == "DRESS-EVE-001"

    @pytest.mark.asyncio
    async def test_ingest_computes_quality_score(
        self,
        use_case: IngestProductUseCase,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingestion should compute an initial quality score > 0."""
        result = await use_case.execute(valid_command)

        assert result.success is True
        assert result.value is not None
        assert result.value.quality_score > 0.0
        assert result.value.quality_score <= 1.0

    @pytest.mark.asyncio
    async def test_ingest_publishes_ingested_event(
        self,
        use_case: IngestProductUseCase,
        event_bus: InMemoryEventBus,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingestion should publish a ProductIngestedEvent."""
        await use_case.execute(valid_command)

        assert len(event_bus.published_events) > 0
        ingested_events = [
            e for e in event_bus.published_events if isinstance(e, ProductIngestedEvent)
        ]
        assert len(ingested_events) == 1
        assert ingested_events[0].sku == "DRESS-EVE-001"
        assert ingested_events[0].source == "ucp"

    @pytest.mark.asyncio
    async def test_ingest_parses_image_uris(
        self,
        use_case: IngestProductUseCase,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingestion should parse GCS image URIs into the product."""
        result = await use_case.execute(valid_command)

        assert result.success is True
        assert result.value is not None
        assert len(result.value.image_uris) == 1
        assert "prism-assets" in result.value.image_uris[0]

    @pytest.mark.asyncio
    async def test_ingest_sets_price(
        self,
        use_case: IngestProductUseCase,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingestion should correctly set the product price."""
        result = await use_case.execute(valid_command)

        assert result.success is True
        assert result.value is not None
        assert result.value.price_amount == 2450.00
        assert result.value.price_currency == "EUR"

    @pytest.mark.asyncio
    async def test_ingest_returns_product_dto(
        self,
        use_case: IngestProductUseCase,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingestion should return a fully populated ProductDTO."""
        result = await use_case.execute(valid_command)

        assert result.success is True
        dto = result.value
        assert dto is not None
        assert dto.id  # non-empty UUID
        assert dto.tenant_id == "tenant-luxe-001"
        assert dto.category == "Clothing"
        assert dto.subcategory == "Dresses"
        assert dto.taxonomy_codes == ("LUX.RTW.DRESS.EVENING",)


# ── Validation / Error Tests ─────────────────────────────────────────


class TestIngestProductValidation:
    """Tests for ingestion validation and error handling."""

    @pytest.mark.asyncio
    async def test_duplicate_sku_rejected(
        self,
        use_case: IngestProductUseCase,
        valid_command: IngestProductCommand,
    ) -> None:
        """Ingesting a duplicate SKU for the same tenant should fail."""
        # First ingestion succeeds
        result1 = await use_case.execute(valid_command)
        assert result1.success is True

        # Second ingestion with same SKU fails
        result2 = await use_case.execute(valid_command)
        assert result2.success is False
        assert result2.error_code == "DUPLICATE_SKU"
        assert "DRESS-EVE-001" in (result2.error or "")

    @pytest.mark.asyncio
    async def test_invalid_currency_rejected(
        self, use_case: IngestProductUseCase
    ) -> None:
        """An unsupported currency code should fail validation."""
        command = IngestProductCommand(
            tenant_id="tenant-luxe-001",
            sku="INVALID-CUR-001",
            name="Test Product",
            brand="Test",
            price_amount=100.00,
            price_currency="XYZ",  # invalid
        )
        result = await use_case.execute(command)

        assert result.success is False
        assert result.error_code == "INVALID_CURRENCY"

    @pytest.mark.asyncio
    async def test_same_sku_different_tenants_allowed(
        self, use_case: IngestProductUseCase
    ) -> None:
        """The same SKU should be allowed for different tenants."""
        command1 = IngestProductCommand(
            tenant_id="tenant-a",
            sku="SHARED-SKU-001",
            name="Product A",
            brand="Brand A",
        )
        command2 = IngestProductCommand(
            tenant_id="tenant-b",
            sku="SHARED-SKU-001",
            name="Product B",
            brand="Brand B",
        )

        result1 = await use_case.execute(command1)
        result2 = await use_case.execute(command2)

        assert result1.success is True
        assert result2.success is True

    @pytest.mark.asyncio
    async def test_minimal_product_ingestion(
        self, use_case: IngestProductUseCase
    ) -> None:
        """A product with only required fields should ingest successfully."""
        command = IngestProductCommand(
            tenant_id="tenant-luxe-001",
            sku="MINIMAL-001",
            name="Minimal Product",
            brand="Test Brand",
        )
        result = await use_case.execute(command)

        assert result.success is True
        assert result.value is not None
        assert result.value.sku == "MINIMAL-001"
        assert result.value.price_amount is None
        assert result.value.image_uris == ()
