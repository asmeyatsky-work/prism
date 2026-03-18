"""
Try-On Context — Mock Virtual Try-On Adapters

Provides mock implementations of:
- BodyExtractionPort  -> MockBodyExtractor
- CompositionPort     -> MockCompositor
- StyleMatchingPort   -> MockStyleMatcher

Returns realistic body pose keypoints, placeholder composition URLs,
and curated outfit suggestions for luxury retail demonstrations.
"""

from __future__ import annotations

import random
import uuid

from prism.shared.domain.value_objects import ImageRef

from prism.tryon.domain.value_objects.composition import (
    BodyPose,
    BrandTryOnConfig,
    ProductOverlay,
    TryOnComposition,
)
from prism.tryon.domain.value_objects.styling import OutfitComposition


class MockBodyExtractor:
    """
    Mock body extraction that returns a realistic front-facing body pose
    with standard fashion-model proportions. Keypoints use normalised
    coordinates (0.0-1.0) suitable for garment overlay positioning.
    """

    async def extract_pose(self, image_bytes: bytes) -> BodyPose:
        # Realistic front-facing body pose keypoints
        # (x, y, confidence) where x/y are normalised 0.0-1.0
        keypoints = {
            "nose": (0.50, 0.08, 0.97),
            "left_eye": (0.47, 0.06, 0.96),
            "right_eye": (0.53, 0.06, 0.96),
            "left_ear": (0.43, 0.07, 0.91),
            "right_ear": (0.57, 0.07, 0.91),
            "left_shoulder": (0.35, 0.18, 0.95),
            "right_shoulder": (0.65, 0.18, 0.95),
            "left_elbow": (0.28, 0.35, 0.93),
            "right_elbow": (0.72, 0.35, 0.93),
            "left_wrist": (0.25, 0.48, 0.90),
            "right_wrist": (0.75, 0.48, 0.90),
            "left_hip": (0.40, 0.52, 0.94),
            "right_hip": (0.60, 0.52, 0.94),
            "left_knee": (0.38, 0.72, 0.92),
            "right_knee": (0.62, 0.72, 0.92),
            "left_ankle": (0.37, 0.92, 0.88),
            "right_ankle": (0.63, 0.92, 0.88),
        }

        return BodyPose(
            keypoints=keypoints,
            orientation="front",
            body_type=random.choice(["standard", "standard", "standard", "athletic"]),
        )


class MockCompositor:
    """
    Mock try-on compositor that returns a TryOnComposition with a
    placeholder signed URL and high confidence score (0.88-0.94).
    Simulates the output of Imagen/Gemini composition pipeline.
    """

    async def compose_tryon(
        self,
        pose: BodyPose,
        product_image: ImageRef,
        config: BrandTryOnConfig,
    ) -> TryOnComposition:
        composition_id = uuid.uuid4().hex[:12]
        # Generate a realistic-looking signed URL placeholder
        signed_url = (
            f"https://storage.googleapis.com/prism-tryon-results-demo/"
            f"compositions/{composition_id}.png"
            f"?X-Goog-Algorithm=GOOG4-RSA-SHA256"
            f"&X-Goog-Expires=3600"
            f"&X-Goog-SignedHeaders=host"
            f"&X-Goog-Signature=demo_signature_{composition_id}"
        )

        product_id = product_image.path.split("/")[-1].replace(".jpg", "").replace(".png", "")

        overlay = ProductOverlay(
            product_id=product_id or f"prod_{composition_id}",
            position=(0.50, 0.42),
            scale=0.85,
            rotation=0.0,
        )

        confidence = round(random.uniform(0.88, 0.94), 3)

        return TryOnComposition(
            result_image_url=signed_url,
            confidence=confidence,
            body_pose=pose,
            product_overlay=overlay,
        )


# ── Curated outfit sets for "Complete the Look" ────────────────────────

_OUTFIT_SETS: list[dict[str, object]] = [
    {
        "occasion": "cocktail_reception",
        "items": (
            "prod_valentino_gown_013",
            "prod_louboutin_kate_011",
            "prod_tiffany_pendant_020",
            "prod_chanel_classic_007",
        ),
        "score": 0.92,
    },
    {
        "occasion": "business_formal",
        "items": (
            "prod_burberry_trench_014",
            "prod_prada_galleria_008",
            "prod_cartier_tank_016",
            "prod_celine_triomphe_019",
        ),
        "score": 0.89,
    },
    {
        "occasion": "casual_luxury",
        "items": (
            "prod_gucci_ace_009",
            "prod_bottega_cassette_006",
            "prod_hermes_carre_018",
        ),
        "score": 0.87,
    },
    {
        "occasion": "resort_weekend",
        "items": (
            "prod_gucci_flora_012",
            "prod_gucci_diana_001",
            "prod_hermes_carre_018",
            "prod_lv_archlight_010",
        ),
        "score": 0.91,
    },
    {
        "occasion": "gallery_opening",
        "items": (
            "prod_maxmara_teddy_015",
            "prod_dior_saddle_005",
            "prod_tiffany_pendant_020",
        ),
        "score": 0.88,
    },
    {
        "occasion": "evening_gala",
        "items": (
            "prod_valentino_gown_013",
            "prod_chanel_classic_007",
            "prod_cartier_tank_016",
            "prod_tiffany_pendant_020",
        ),
        "score": 0.94,
    },
]


class MockStyleMatcher:
    """
    Mock style matching that returns curated outfit compositions
    from a set of pre-defined luxury looks. Rotates through outfit
    sets and ensures the seed product is always included.
    """

    async def suggest_outfit(
        self,
        product_id: str,
        catalogue_context: dict[str, object],
    ) -> OutfitComposition:
        # Pick a random outfit set
        outfit_data = random.choice(_OUTFIT_SETS)
        items = list(outfit_data["items"])  # type: ignore[arg-type]

        # Ensure the seed product is included
        if product_id not in items:
            items[0] = product_id

        return OutfitComposition(
            items=tuple(items),
            style_score=float(outfit_data["score"]),  # type: ignore[arg-type]
            occasion=str(outfit_data["occasion"]),
        )
