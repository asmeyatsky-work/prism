"""
Product Aggregate Root — Domain Unit Tests

Pure domain tests with no mocks, no infrastructure. These tests verify:
- Product creation via factory method
- Enrichment lifecycle transitions
- Quality score updates
- Image management
- Taxonomy updates
- Review workflow
- Immutability enforcement
- Domain event emission on state transitions

All tests operate on frozen dataclass instances and verify that mutations
return new instances while preserving the original.
"""

from __future__ import annotations

import pytest

from prism.catalogue.domain.entities.product import EnrichmentStatus, Product
from prism.catalogue.domain.events.catalogue_events import (
    ProductEnrichedEvent,
    ProductIngestedEvent,
    ProductReviewedEvent,
)
from prism.catalogue.domain.services.quality_service import QualityService
from prism.shared.domain.value_objects import (
    Currency,
    ImageRef,
    Money,
    TenantId,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def tenant_id() -> TenantId:
    """Standard test tenant."""
    return TenantId(value="tenant-luxe-001")


@pytest.fixture
def sample_image() -> ImageRef:
    """A sample product image reference."""
    return ImageRef(
        bucket="prism-assets",
        path="products/dress-001/front.jpg",
        content_type="image/jpeg",
    )


@pytest.fixture
def sample_price() -> Money:
    """A sample luxury product price."""
    return Money(amount=2450.00, currency=Currency.EUR)


@pytest.fixture
def raw_product(tenant_id: TenantId, sample_image: ImageRef, sample_price: Money) -> Product:
    """A freshly ingested (RAW) product with basic data."""
    return Product.create(
        tenant_id=tenant_id,
        sku="DRESS-EVE-001",
        name="Midnight Silk Evening Dress",
        brand="Maison Lumiere",
        description="An exquisite evening dress crafted from pure silk.",
        category="Clothing",
        subcategory="Dresses",
        attributes={"material": "silk", "colour": "midnight blue"},
        images=(sample_image,),
        price=sample_price,
        taxonomy_codes=("LUX.RTW.DRESS.EVENING",),
        source="ucp",
    )


@pytest.fixture
def quality_service() -> QualityService:
    """Quality scoring domain service."""
    return QualityService()


# ── Product Creation Tests ───────────────────────────────────────────


class TestProductCreation:
    """Tests for Product.create() factory method."""

    def test_create_product_sets_all_fields(
        self, tenant_id: TenantId, sample_image: ImageRef, sample_price: Money
    ) -> None:
        """Product.create() should populate all provided fields correctly."""
        product = Product.create(
            tenant_id=tenant_id,
            sku="BAG-TOTE-001",
            name="Artisan Leather Tote",
            brand="Maison Lumiere",
            description="Hand-stitched Italian leather tote.",
            category="Accessories",
            subcategory="Handbags",
            attributes={"material": "leather", "colour": "cognac"},
            images=(sample_image,),
            price=sample_price,
            taxonomy_codes=("LUX.ACC.BAG.TOTE",),
            source="manual",
        )

        assert product.sku == "BAG-TOTE-001"
        assert product.name == "Artisan Leather Tote"
        assert product.brand == "Maison Lumiere"
        assert product.category == "Accessories"
        assert product.subcategory == "Handbags"
        assert product.attributes == {"material": "leather", "colour": "cognac"}
        assert len(product.images) == 1
        assert product.price == sample_price
        assert product.taxonomy_codes == ("LUX.ACC.BAG.TOTE",)
        assert product.tenant_id == tenant_id

    def test_create_product_starts_as_raw(self, tenant_id: TenantId) -> None:
        """Newly created products should be in RAW enrichment status."""
        product = Product.create(
            tenant_id=tenant_id,
            sku="SCARF-001",
            name="Cashmere Scarf",
            brand="Maison Lumiere",
        )
        assert product.enrichment_status == EnrichmentStatus.RAW

    def test_create_product_has_zero_quality_score(self, tenant_id: TenantId) -> None:
        """Newly created products should have a quality score of 0.0."""
        product = Product.create(
            tenant_id=tenant_id,
            sku="SCARF-002",
            name="Wool Scarf",
            brand="Maison Lumiere",
        )
        assert product.quality_score == 0.0

    def test_create_product_has_valid_id(self, tenant_id: TenantId) -> None:
        """Newly created products should have a non-empty UUID string ID."""
        product = Product.create(
            tenant_id=tenant_id,
            sku="SCARF-003",
            name="Silk Scarf",
            brand="Maison Lumiere",
        )
        assert product.id
        assert isinstance(product.id, str)
        assert len(product.id) == 36  # UUID format

    def test_create_product_emits_ingested_event(self, raw_product: Product) -> None:
        """Product.create() should emit a ProductIngestedEvent."""
        assert len(raw_product.domain_events) == 1
        event = raw_product.domain_events[0]
        assert isinstance(event, ProductIngestedEvent)
        assert event.sku == "DRESS-EVE-001"
        assert event.brand == "Maison Lumiere"
        assert event.source == "ucp"
        assert event.aggregate_id == raw_product.id
        assert event.tenant_id == "tenant-luxe-001"


# ── Enrichment Tests ─────────────────────────────────────────────────


class TestProductEnrichment:
    """Tests for the enrichment lifecycle."""

    def test_enrich_merges_attributes(self, raw_product: Product) -> None:
        """Enrichment should merge new attributes with existing ones."""
        enriched = raw_product.enrich({"pattern": "solid", "silhouette": "A-line"})

        assert enriched.attributes["material"] == "silk"  # preserved
        assert enriched.attributes["colour"] == "midnight blue"  # preserved
        assert enriched.attributes["pattern"] == "solid"  # new
        assert enriched.attributes["silhouette"] == "A-line"  # new

    def test_enrich_transitions_to_enriched_status(self, raw_product: Product) -> None:
        """Enrichment should transition the product to ENRICHED status."""
        enriched = raw_product.enrich({"pattern": "solid"})
        assert enriched.enrichment_status == EnrichmentStatus.ENRICHED

    def test_enrich_emits_enriched_event(self, raw_product: Product) -> None:
        """Enrichment should emit a ProductEnrichedEvent."""
        enriched = raw_product.enrich({"pattern": "solid", "occasion": "evening"})

        # Should have the original ingestion event plus the enrichment event
        assert len(enriched.domain_events) == 2
        event = enriched.domain_events[1]
        assert isinstance(event, ProductEnrichedEvent)
        assert event.sku == "DRESS-EVE-001"
        assert set(event.enriched_fields) == {"pattern", "occasion"}

    def test_enrich_preserves_original_product(self, raw_product: Product) -> None:
        """Enrichment should return a new instance — original is unchanged."""
        enriched = raw_product.enrich({"pattern": "solid"})

        assert raw_product.enrichment_status == EnrichmentStatus.RAW
        assert "pattern" not in raw_product.attributes
        assert enriched is not raw_product

    def test_cannot_enrich_reviewed_product(self, raw_product: Product) -> None:
        """A REVIEWED product cannot be re-enriched."""
        enriched = raw_product.enrich({"pattern": "solid"})
        reviewed = enriched.mark_as_reviewed(reviewer_id="reviewer-001")

        with pytest.raises(ValueError, match="already been reviewed"):
            reviewed.enrich({"new_field": "value"})


# ── Quality Score Tests ──────────────────────────────────────────────


class TestQualityScore:
    """Tests for quality score updates and the quality service."""

    def test_update_quality_score(self, raw_product: Product) -> None:
        """update_quality_score should return a new product with the updated score."""
        updated = raw_product.update_quality_score(0.75)
        assert updated.quality_score == 0.75
        assert raw_product.quality_score == 0.0  # original unchanged

    def test_quality_score_rejects_out_of_range(self, raw_product: Product) -> None:
        """Quality scores outside [0.0, 1.0] should be rejected."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            raw_product.update_quality_score(1.5)

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            raw_product.update_quality_score(-0.1)

    def test_quality_service_scores_completeness(
        self, quality_service: QualityService, raw_product: Product
    ) -> None:
        """Quality service should give higher scores to more complete products."""
        # raw_product has material and colour attributes
        score = quality_service.calculate_quality_score(raw_product)
        assert score > 0.0

        # A product with no attributes should score lower
        minimal_product = Product.create(
            tenant_id=TenantId(value="tenant-luxe-001"),
            sku="MINIMAL-001",
            name="Minimal Product",
            brand="Test",
        )
        minimal_score = quality_service.calculate_quality_score(minimal_product)
        assert minimal_score < score

    def test_quality_service_values_images(
        self, quality_service: QualityService, tenant_id: TenantId
    ) -> None:
        """Products with images should score higher than those without."""
        no_images = Product.create(
            tenant_id=tenant_id,
            sku="NO-IMG-001",
            name="No Image Product",
            brand="Test",
            description="A product without images.",
        )
        with_images = Product.create(
            tenant_id=tenant_id,
            sku="IMG-001",
            name="With Image Product",
            brand="Test",
            description="A product with images.",
            images=(
                ImageRef(bucket="b", path="1.jpg"),
                ImageRef(bucket="b", path="2.jpg"),
            ),
        )

        score_no_img = quality_service.calculate_quality_score(no_images)
        score_with_img = quality_service.calculate_quality_score(with_images)
        assert score_with_img > score_no_img

    def test_quality_service_returns_bounded_score(
        self, quality_service: QualityService, raw_product: Product
    ) -> None:
        """Quality score should always be between 0.0 and 1.0."""
        score = quality_service.calculate_quality_score(raw_product)
        assert 0.0 <= score <= 1.0


# ── Image Management Tests ───────────────────────────────────────────


class TestImageManagement:
    """Tests for product image operations."""

    def test_add_image(self, raw_product: Product) -> None:
        """add_image should append to the images tuple."""
        new_image = ImageRef(
            bucket="prism-assets",
            path="products/dress-001/back.jpg",
        )
        updated = raw_product.add_image(new_image)

        assert len(updated.images) == 2
        assert updated.images[1] == new_image
        assert len(raw_product.images) == 1  # original unchanged

    def test_add_multiple_images(self, raw_product: Product) -> None:
        """Multiple add_image calls should accumulate correctly."""
        img2 = ImageRef(bucket="b", path="2.jpg")
        img3 = ImageRef(bucket="b", path="3.jpg")

        updated = raw_product.add_image(img2).add_image(img3)
        assert len(updated.images) == 3


# ── Taxonomy Tests ───────────────────────────────────────────────────


class TestTaxonomy:
    """Tests for taxonomy updates."""

    def test_update_taxonomy(self, raw_product: Product) -> None:
        """update_taxonomy should replace taxonomy codes."""
        new_codes = ("LUX.RTW.DRESS.COCKTAIL", "GS1.10000043")
        updated = raw_product.update_taxonomy(new_codes)

        assert updated.taxonomy_codes == new_codes
        assert raw_product.taxonomy_codes == ("LUX.RTW.DRESS.EVENING",)

    def test_update_taxonomy_to_empty(self, raw_product: Product) -> None:
        """Taxonomy can be cleared by setting to empty tuple."""
        updated = raw_product.update_taxonomy(())
        assert updated.taxonomy_codes == ()


# ── Review Workflow Tests ────────────────────────────────────────────


class TestReviewWorkflow:
    """Tests for the product review lifecycle."""

    def test_mark_as_reviewed(self, raw_product: Product) -> None:
        """An ENRICHED product can be marked as reviewed."""
        enriched = raw_product.enrich({"pattern": "solid"})
        reviewed = enriched.mark_as_reviewed(reviewer_id="reviewer-001")

        assert reviewed.enrichment_status == EnrichmentStatus.REVIEWED

    def test_review_emits_reviewed_event(self, raw_product: Product) -> None:
        """mark_as_reviewed should emit a ProductReviewedEvent."""
        enriched = raw_product.enrich({"pattern": "solid"})
        reviewed = enriched.mark_as_reviewed(reviewer_id="reviewer-001")

        # Ingested + Enriched + Reviewed = 3 events
        assert len(reviewed.domain_events) == 3
        event = reviewed.domain_events[2]
        assert isinstance(event, ProductReviewedEvent)
        assert event.reviewer_id == "reviewer-001"
        assert event.sku == "DRESS-EVE-001"

    def test_cannot_review_raw_product(self, raw_product: Product) -> None:
        """A RAW product cannot be reviewed — must be enriched first."""
        with pytest.raises(ValueError, match="Only ENRICHED products"):
            raw_product.mark_as_reviewed(reviewer_id="reviewer-001")

    def test_cannot_review_already_reviewed_product(self, raw_product: Product) -> None:
        """A REVIEWED product cannot be reviewed again."""
        enriched = raw_product.enrich({"pattern": "solid"})
        reviewed = enriched.mark_as_reviewed(reviewer_id="reviewer-001")

        with pytest.raises(ValueError, match="Only ENRICHED products"):
            reviewed.mark_as_reviewed(reviewer_id="reviewer-002")


# ── Immutability Tests ───────────────────────────────────────────────


class TestImmutability:
    """Tests verifying that Product instances are truly immutable."""

    def test_cannot_set_attribute_directly(self, raw_product: Product) -> None:
        """Direct attribute assignment should raise FrozenInstanceError."""
        with pytest.raises(AttributeError):
            raw_product.name = "Modified Name"  # type: ignore[misc]

    def test_cannot_set_status_directly(self, raw_product: Product) -> None:
        """Direct status assignment should raise FrozenInstanceError."""
        with pytest.raises(AttributeError):
            raw_product.enrichment_status = EnrichmentStatus.ENRICHED  # type: ignore[misc]

    def test_domain_methods_return_new_instances(self, raw_product: Product) -> None:
        """All domain methods should return new instances, not modify in-place."""
        updated_score = raw_product.update_quality_score(0.5)
        assert updated_score is not raw_product

        new_image = ImageRef(bucket="b", path="new.jpg")
        with_image = raw_product.add_image(new_image)
        assert with_image is not raw_product

        new_taxonomy = raw_product.update_taxonomy(("NEW.CODE",))
        assert new_taxonomy is not raw_product

    def test_clear_events_returns_new_instance(self, raw_product: Product) -> None:
        """clear_events should return a new instance with empty events."""
        cleared = raw_product.clear_events()
        assert cleared is not raw_product
        assert len(cleared.domain_events) == 0
        assert len(raw_product.domain_events) == 1  # original has event
