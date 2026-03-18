"""
Try-On Domain — Composition Value Objects

Architectural Intent:
- Immutable value objects representing the output of the virtual try-on pipeline
- BodyPose captures extracted pose keypoints without retaining the source image
- TryOnComposition holds the final composited result with a signed URL (ephemeral)
- BrandTryOnConfig encapsulates tenant-specific rendering preferences
- All objects are frozen dataclasses — equality is structural per skill2026 Rule 3

Privacy-by-design:
- BodyPose contains only extracted keypoints, never raw image data
- TryOnComposition.result_image_url is a time-limited signed URL, not a permanent asset
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.value_objects import ImageRef, ValueObject


@dataclass(frozen=True)
class BodyPose(ValueObject):
    """
    Extracted body pose representation from a customer image.

    Contains only derived keypoint data — the source image bytes are
    discarded immediately after extraction (GDPR / privacy-by-design).

    Attributes:
        keypoints: Mapping of body landmark names to (x, y, confidence) tuples.
        orientation: Detected body orientation (e.g. "front", "side", "back").
        body_type: Inferred body silhouette category for garment fitting.
    """

    keypoints: dict[str, tuple[float, float, float]] = field(default_factory=dict)
    orientation: str = "front"
    body_type: str = "standard"

    def __post_init__(self) -> None:
        if self.orientation not in ("front", "side", "back", "three_quarter"):
            raise ValueError(
                f"Invalid orientation '{self.orientation}'; "
                "must be one of: front, side, back, three_quarter"
            )


@dataclass(frozen=True)
class ProductOverlay(ValueObject):
    """
    Describes how a product image is positioned over the body pose.

    Attributes:
        product_id: The product being overlaid.
        position: (x, y) normalised anchor coordinates on the composition canvas.
        scale: Scaling factor applied to the product image.
        rotation: Rotation angle in degrees for alignment with the body pose.
    """

    product_id: str = ""
    position: tuple[float, float] = (0.5, 0.5)
    scale: float = 1.0
    rotation: float = 0.0

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("Product overlay scale must be positive")
        if not self.product_id:
            raise ValueError("ProductOverlay requires a product_id")


@dataclass(frozen=True)
class TryOnComposition(ValueObject):
    """
    Final virtual try-on result delivered to the client.

    The result_image_url is a time-limited signed URL. The underlying
    composited image is stored ephemerally and auto-deleted after expiry.

    Attributes:
        result_image_url: Signed URL to the composited try-on image.
        confidence: Model confidence score for the composition (0.0-1.0).
        body_pose: The pose data used to generate this composition.
        product_overlay: Product positioning parameters applied.
    """

    result_image_url: str = ""
    confidence: float = 0.0
    body_pose: BodyPose = field(default_factory=BodyPose)
    product_overlay: ProductOverlay | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass(frozen=True)
class BrandTryOnConfig(ValueObject):
    """
    Tenant-specific configuration for virtual try-on rendering.

    Each luxury brand can customise the visual presentation of try-on results
    to match their brand identity — background, lighting, and watermark.

    Attributes:
        background_preset: Named background style (e.g. "studio_white", "lifestyle_urban").
        lighting_preset: Named lighting configuration (e.g. "soft_diffused", "dramatic").
        watermark_enabled: Whether to apply a brand watermark to the result.
        watermark_image: Optional reference to the brand's watermark asset.
    """

    background_preset: str = "studio_white"
    lighting_preset: str = "soft_diffused"
    watermark_enabled: bool = False
    watermark_image: ImageRef | None = None

    def __post_init__(self) -> None:
        if self.watermark_enabled and self.watermark_image is None:
            raise ValueError(
                "watermark_image must be provided when watermark_enabled is True"
            )
