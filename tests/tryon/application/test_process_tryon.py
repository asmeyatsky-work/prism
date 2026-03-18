"""
Tests for ProcessTryOnUseCase

Tests cover:
- Happy path: full pipeline execution with mocked ports
- Consent validation: rejected when consent=False
- Category validation: rejected for unsupported categories
- Body extraction failure handling
- Composition failure handling
- Privacy: customer image bytes not stored in result
- Latency budget tracking
"""

from __future__ import annotations

import pytest

from prism.shared.application.dtos import CommandResult
from prism.shared.domain.value_objects import ImageRef

from prism.tryon.application.commands.process_tryon import ProcessTryOnUseCase
from prism.tryon.application.dtos.tryon_dto import TryOnRequestDTO, TryOnResponseDTO
from prism.tryon.domain.value_objects.composition import (
    BodyPose,
    BrandTryOnConfig,
    ProductOverlay,
    TryOnComposition,
)


# --- Test Doubles (in-memory fakes implementing Protocol ports) ---


class FakeBodyExtractor:
    """In-memory fake implementing BodyExtractionPort."""

    def __init__(
        self,
        pose: BodyPose | None = None,
        error: Exception | None = None,
    ) -> None:
        self._pose = pose or BodyPose(
            keypoints={
                "left_shoulder": (0.3, 0.4, 0.95),
                "right_shoulder": (0.7, 0.4, 0.93),
                "neck": (0.5, 0.3, 0.97),
            },
            orientation="front",
            body_type="standard",
        )
        self._error = error
        self.extract_calls: list[int] = []  # Track byte lengths, NOT actual bytes

    async def extract_pose(self, image_bytes: bytes) -> BodyPose:
        # Record the call (byte length only — privacy)
        self.extract_calls.append(len(image_bytes))
        if self._error:
            raise self._error
        return self._pose


class FakeCompositor:
    """In-memory fake implementing CompositionPort."""

    def __init__(
        self,
        composition: TryOnComposition | None = None,
        error: Exception | None = None,
    ) -> None:
        self._composition = composition or TryOnComposition(
            result_image_url="https://storage.example.com/signed/result.png",
            confidence=0.91,
            body_pose=BodyPose(
                keypoints={"neck": (0.5, 0.3, 0.97)},
                orientation="front",
            ),
            product_overlay=ProductOverlay(product_id="product-123"),
        )
        self._error = error
        self.compose_calls: list[tuple[BodyPose, ImageRef, BrandTryOnConfig]] = []

    async def compose_tryon(
        self,
        pose: BodyPose,
        product_image: ImageRef,
        config: BrandTryOnConfig,
    ) -> TryOnComposition:
        self.compose_calls.append((pose, product_image, config))
        if self._error:
            raise self._error
        return self._composition


# --- Fixtures ---


def _make_request(**overrides) -> TryOnRequestDTO:
    """Create a TryOnRequestDTO with sensible defaults."""
    defaults = {
        "customer_image": b"\xff\xd8fake-jpeg-bytes",
        "product_id": "product-123",
        "tenant_id": "tenant-gucci",
        "consent": True,
        "category": "APPAREL",
    }
    defaults.update(overrides)
    return TryOnRequestDTO(**defaults)


def _make_product_image() -> ImageRef:
    return ImageRef(bucket="prism-catalogue", path="products/product-123.jpg")


# --- Happy Path ---


class TestProcessTryOnHappyPath:
    """Test the full try-on pipeline with successful execution."""

    @pytest.mark.asyncio
    async def test_successful_tryon_returns_ok(self):
        extractor = FakeBodyExtractor()
        compositor = FakeCompositor()
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=compositor,
        )

        result = await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert result.success is True
        assert result.value is not None
        assert isinstance(result.value, TryOnResponseDTO)
        assert result.value.product_id == "product-123"
        assert result.value.result_image_url == "https://storage.example.com/signed/result.png"
        assert result.value.confidence == 0.91

    @pytest.mark.asyncio
    async def test_body_extractor_called_with_image_bytes(self):
        extractor = FakeBodyExtractor()
        compositor = FakeCompositor()
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=compositor,
        )

        await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert len(extractor.extract_calls) == 1
        assert extractor.extract_calls[0] == len(b"\xff\xd8fake-jpeg-bytes")

    @pytest.mark.asyncio
    async def test_compositor_called_with_pose_and_config(self):
        extractor = FakeBodyExtractor()
        compositor = FakeCompositor()
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=compositor,
        )

        await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert len(compositor.compose_calls) == 1
        pose, product_image, config = compositor.compose_calls[0]
        assert isinstance(pose, BodyPose)
        assert product_image.bucket == "prism-catalogue"
        assert config.background_preset == "studio_white"

    @pytest.mark.asyncio
    async def test_processing_time_is_tracked(self):
        extractor = FakeBodyExtractor()
        compositor = FakeCompositor()
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=compositor,
        )

        result = await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert result.value is not None
        assert result.value.processing_time_ms >= 0


# --- Consent Validation ---


class TestConsentValidation:
    """Test that consent is required for image processing."""

    @pytest.mark.asyncio
    async def test_rejected_without_consent(self):
        use_case = ProcessTryOnUseCase(
            body_extractor=FakeBodyExtractor(),
            compositor=FakeCompositor(),
        )

        result = await use_case.execute(
            request=_make_request(consent=False),
            product_image=_make_product_image(),
        )

        assert result.success is False
        assert result.error_code == "CONSENT_REQUIRED"
        assert "consent" in result.error.lower()

    @pytest.mark.asyncio
    async def test_no_extraction_called_without_consent(self):
        extractor = FakeBodyExtractor()
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=FakeCompositor(),
        )

        await use_case.execute(
            request=_make_request(consent=False),
            product_image=_make_product_image(),
        )

        assert len(extractor.extract_calls) == 0


# --- Category Validation ---


class TestCategoryValidation:
    """Test that unsupported categories are rejected."""

    @pytest.mark.asyncio
    async def test_unsupported_category_rejected(self):
        use_case = ProcessTryOnUseCase(
            body_extractor=FakeBodyExtractor(),
            compositor=FakeCompositor(),
        )

        result = await use_case.execute(
            request=_make_request(category="FURNITURE"),
            product_image=_make_product_image(),
        )

        assert result.success is False
        assert result.error_code == "UNSUPPORTED_CATEGORY"

    @pytest.mark.asyncio
    async def test_all_valid_categories_accepted(self):
        for category in ("APPAREL", "ACCESSORIES", "EYEWEAR", "JEWELLERY"):
            use_case = ProcessTryOnUseCase(
                body_extractor=FakeBodyExtractor(),
                compositor=FakeCompositor(),
            )

            result = await use_case.execute(
                request=_make_request(category=category),
                product_image=_make_product_image(),
            )

            assert result.success is True, f"Category {category} should be accepted"


# --- Error Handling ---


class TestErrorHandling:
    """Test failure scenarios in the pipeline."""

    @pytest.mark.asyncio
    async def test_body_extraction_failure(self):
        extractor = FakeBodyExtractor(error=ValueError("No body detected"))
        use_case = ProcessTryOnUseCase(
            body_extractor=extractor,
            compositor=FakeCompositor(),
        )

        result = await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert result.success is False
        assert result.error_code == "EXTRACTION_FAILED"
        assert "No body detected" in result.error

    @pytest.mark.asyncio
    async def test_composition_failure(self):
        compositor = FakeCompositor(error=RuntimeError("Imagen API timeout"))
        use_case = ProcessTryOnUseCase(
            body_extractor=FakeBodyExtractor(),
            compositor=compositor,
        )

        result = await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert result.success is False
        assert result.error_code == "COMPOSITION_FAILED"
        assert "Imagen API timeout" in result.error

    @pytest.mark.asyncio
    async def test_compositor_not_called_on_extraction_failure(self):
        compositor = FakeCompositor()
        use_case = ProcessTryOnUseCase(
            body_extractor=FakeBodyExtractor(error=RuntimeError("GPU OOM")),
            compositor=compositor,
        )

        await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert len(compositor.compose_calls) == 0


# --- Privacy ---


class TestPrivacy:
    """Verify that customer image bytes are not leaked into results."""

    @pytest.mark.asyncio
    async def test_response_contains_no_image_bytes(self):
        use_case = ProcessTryOnUseCase(
            body_extractor=FakeBodyExtractor(),
            compositor=FakeCompositor(),
        )

        result = await use_case.execute(
            request=_make_request(),
            product_image=_make_product_image(),
        )

        assert result.success is True
        # The response DTO should only have metadata, not image bytes
        response_json = result.value.model_dump_json()
        assert b"\xff\xd8" not in response_json.encode()
        assert "fake-jpeg" not in response_json

    def test_request_dto_excludes_image_from_serialisation(self):
        request = _make_request()
        serialised = request.model_dump()
        assert "customer_image" not in serialised

    def test_request_dto_excludes_image_from_json(self):
        request = _make_request()
        json_str = request.model_dump_json()
        assert "customer_image" not in json_str
        assert "fake-jpeg" not in json_str
