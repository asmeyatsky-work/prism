"""
Try-On Domain Ports — Protocol-based interfaces

Architectural Intent:
- Protocol classes define the contracts between domain/application and infrastructure
- Infrastructure adapters implement these protocols (Gemini, Imagen, etc.)
- Dependency inversion: domain depends on abstractions, not concrete implementations
- Ports accept raw bytes for customer images — bytes are processed in-memory
  and NEVER persisted (GDPR / privacy-by-design)

Port Inventory:
- BodyExtractionPort: extract pose keypoints from customer image bytes
- CompositionPort: compose virtual try-on from pose + product image
- StyleMatchingPort: suggest complementary outfit items
"""

from __future__ import annotations

from typing import Protocol

from prism.shared.domain.value_objects import ImageRef

from prism.tryon.domain.value_objects.composition import (
    BodyPose,
    BrandTryOnConfig,
    TryOnComposition,
)
from prism.tryon.domain.value_objects.styling import OutfitComposition


class BodyExtractionPort(Protocol):
    """
    Port for extracting body pose from a customer image.

    Implementations receive raw image bytes, extract pose keypoints,
    and return a BodyPose value object. The image bytes MUST NOT be
    persisted or logged by any implementation.
    """

    async def extract_pose(self, image_bytes: bytes) -> BodyPose:
        """
        Extract body pose keypoints from the provided image bytes.

        Args:
            image_bytes: Raw customer image bytes (JPEG/PNG). These bytes
                are processed in-memory only and must not be stored.

        Returns:
            BodyPose with extracted keypoints, orientation, and body type.

        Raises:
            ValueError: If the image cannot be processed (corrupt, no body detected).
        """
        ...


class CompositionPort(Protocol):
    """
    Port for composing a virtual try-on result.

    Takes an extracted body pose, a product image reference, and brand-specific
    rendering configuration. Returns a composited try-on result with a signed URL.
    """

    async def compose_tryon(
        self,
        pose: BodyPose,
        product_image: ImageRef,
        config: BrandTryOnConfig,
    ) -> TryOnComposition:
        """
        Compose a virtual try-on image.

        Args:
            pose: Extracted body pose keypoints.
            product_image: Reference to the product image in Cloud Storage.
            config: Brand-specific rendering configuration.

        Returns:
            TryOnComposition with signed URL to the composited result.

        Raises:
            RuntimeError: If composition fails (model error, timeout).
        """
        ...


class StyleMatchingPort(Protocol):
    """
    Port for AI-powered outfit suggestion ("Complete the Look").

    Takes a seed product and catalogue context to suggest complementary items.
    """

    async def suggest_outfit(
        self,
        product_id: str,
        catalogue_context: dict[str, object],
    ) -> OutfitComposition:
        """
        Suggest a complete outfit based on a seed product.

        Args:
            product_id: The product the customer is trying on.
            catalogue_context: Additional catalogue metadata (available items,
                brand preferences, season, etc.).

        Returns:
            OutfitComposition with suggested product IDs and style score.

        Raises:
            RuntimeError: If the style matching model is unavailable.
        """
        ...
