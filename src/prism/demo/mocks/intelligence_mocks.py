"""
Intelligence Context — Mock AI Service Adapters

Provides mock implementations of:
- AttributeExtractionPort  -> MockAttributeExtractor
- DescriptionGenerationPort -> MockDescriptionGenerator
- EmbeddingGenerationPort  -> MockEmbeddingGenerator
- VectorIndexPort          -> MockVectorIndex
- ImageQualityPort         -> MockImageQuality

Returns realistic luxury retail AI outputs with high confidence scores,
pre-written brand-voice descriptions, and random embedding vectors.
"""

from __future__ import annotations

import random
import uuid

from prism.intelligence.domain.value_objects.ai_output import (
    AttributeWithConfidence,
    ExtractedAttributes,
    GeneratedDescription,
)
from prism.intelligence.domain.value_objects.model_config import BrandVoiceConfig, Tone
from prism.shared.domain.value_objects import ImageRef, Locale


class MockAttributeExtractor:
    """
    Mock attribute extraction returning realistic luxury product attributes
    with high confidence scores (0.88-0.98 range) to simulate production
    quality AI extraction from Gemini Vision.
    """

    async def extract_attributes(
        self,
        images: list[ImageRef],
        context: dict[str, str],
    ) -> ExtractedAttributes:
        category = context.get("category", "").lower()
        brand = context.get("brand", "")

        # Base materials by category
        if "bag" in category or "leather" in category:
            material = "Nappa lambskin"
        elif "shoe" in category:
            material = "Italian calfskin"
        elif "dress" in category or "gown" in category:
            material = "Silk crepe de chine"
        elif "coat" in category or "jacket" in category:
            material = "Virgin wool-cashmere blend"
        elif "watch" in category:
            material = "Stainless steel with sapphire crystal"
        elif "scarf" in category:
            material = "Silk twill"
        else:
            material = "Italian calfskin leather"

        # Colour selection
        colours = [
            "Nero", "Ivory", "Burgundy", "Midnight Navy",
            "Champagne Gold", "Emerald", "Camel",
        ]
        colour = random.choice(colours)

        # Pattern based on brand hint
        if brand.lower() in ("gucci", "fendi"):
            pattern = "Monogram jacquard"
        elif brand.lower() in ("bottega veneta",):
            pattern = "Intrecciato woven"
        elif brand.lower() in ("burberry",):
            pattern = "Heritage check"
        else:
            pattern = random.choice(["Solid", "Tonal stripe", "Abstract geometric"])

        return ExtractedAttributes(
            material=AttributeWithConfidence(
                value=material,
                confidence=round(random.uniform(0.91, 0.98), 2),
            ),
            colour=AttributeWithConfidence(
                value=colour,
                confidence=round(random.uniform(0.93, 0.99), 2),
            ),
            pattern=AttributeWithConfidence(
                value=pattern,
                confidence=round(random.uniform(0.88, 0.96), 2),
            ),
            silhouette=AttributeWithConfidence(
                value=random.choice([
                    "Structured", "Relaxed", "A-line", "Oversized",
                    "Tailored slim", "Draped", "Column",
                ]),
                confidence=round(random.uniform(0.85, 0.95), 2),
            ),
            occasion=AttributeWithConfidence(
                value=random.choice([
                    "Black-tie evening", "Business formal", "Resort casual",
                    "Weekend brunch", "Gallery opening", "Cocktail reception",
                ]),
                confidence=round(random.uniform(0.82, 0.94), 2),
            ),
            season=AttributeWithConfidence(
                value=random.choice(["SS25", "AW25", "Resort 2025", "Pre-Fall 2025"]),
                confidence=round(random.uniform(0.90, 0.97), 2),
            ),
            style_tags=[
                AttributeWithConfidence(
                    value=tag,
                    confidence=round(random.uniform(0.80, 0.95), 2),
                )
                for tag in random.sample(
                    [
                        "timeless", "investment piece", "day-to-night",
                        "statement", "effortless", "heritage",
                        "modern classic", "artisanal", "collectible",
                    ],
                    k=random.randint(2, 4),
                )
            ],
        )


class MockDescriptionGenerator:
    """
    Mock description generator that produces pre-written luxury copy
    tailored to the brand voice tone: luxury (elaborate), contemporary
    (minimal), or avant-garde (edgy).
    """

    _LUXURY_TEMPLATES = [
        (
            "A masterwork of atelier craftsmanship, this piece from {brand} "
            "is realised in {material}, selected for its extraordinary suppleness "
            "and lustre. The {colour} colourway evokes the quiet grandeur of "
            "Florentine palazzos at dusk, while the {pattern} motif pays homage "
            "to the Maison's storied heritage. An investment in enduring elegance."
        ),
        (
            "Born from {brand}'s unwavering commitment to excellence, this "
            "{material} creation captures the intersection of heritage savoir-faire "
            "and contemporary vision. The {colour} palette lends an air of "
            "sophisticated restraint, perfectly suited for life's most distinguished moments."
        ),
        (
            "The epitome of {brand}'s creative philosophy, this exquisite piece "
            "marries {material} with impeccable construction. Each detail -- from "
            "the hand-finished edges to the {pattern} treatment -- reflects "
            "generations of artisanal expertise passed down through the atelier."
        ),
    ]

    _CONTEMPORARY_TEMPLATES = [
        (
            "{brand}. {material}. {colour}. Nothing more, nothing less. "
            "A piece that lets the craft speak for itself."
        ),
        (
            "Precision-cut {material} in {colour}. {brand} distils luxury to "
            "its purest form -- clean proportions, considered details, zero noise."
        ),
        (
            "From {brand}: {material} meets intention. The {colour} tone pairs "
            "with everything. The {pattern} detail is the only accent you need."
        ),
    ]

    _AVANT_GARDE_TEMPLATES = [
        (
            "Boundaries dissolve. {brand} tears apart the rulebook with "
            "{material} reimagined through a deconstructivist lens. {colour} "
            "bleeds across the {pattern} surface like a manifesto in textile form."
        ),
        (
            "This isn't fashion -- it's a position. {brand} weaponises "
            "{material} and {colour} to create something that demands a reaction. "
            "The {pattern} intervention refuses to comfort."
        ),
        (
            "Radical. Deliberate. {brand} pushes {material} beyond its limits. "
            "The {colour} pigment is applied with controlled chaos, and the "
            "{pattern} construction challenges every assumption about what "
            "luxury means."
        ),
    ]

    async def generate_description(
        self,
        attributes: dict[str, str],
        voice_config: BrandVoiceConfig,
        locale: Locale,
    ) -> GeneratedDescription:
        brand = voice_config.brand_name
        material = attributes.get("material", "the finest materials")
        colour = attributes.get("colour", "a refined tone")
        pattern = attributes.get("pattern", "signature")

        if voice_config.tone == Tone.LUXURY:
            template = random.choice(self._LUXURY_TEMPLATES)
        elif voice_config.tone == Tone.CONTEMPORARY:
            template = random.choice(self._CONTEMPORARY_TEMPLATES)
        elif voice_config.tone == Tone.AVANT_GARDE:
            template = random.choice(self._AVANT_GARDE_TEMPLATES)
        else:
            template = random.choice(self._LUXURY_TEMPLATES)

        text = template.format(
            brand=brand,
            material=material,
            colour=colour,
            pattern=pattern,
        )

        return GeneratedDescription(
            text=text,
            tone=voice_config.tone.value,
            locale=locale.code,
            word_count=len(text.split()),
        )


class MockEmbeddingGenerator:
    """
    Mock embedding generator that returns random normalised vectors.
    Text embeddings are 768-dim; multimodal embeddings are 1024-dim.
    Uses text hash as seed for reproducibility across calls.
    """

    _TEXT_DIMS = 768
    _MULTIMODAL_DIMS = 1024

    async def generate_text_embedding(self, text: str) -> list[float]:
        return self._random_vector(text, self._TEXT_DIMS)

    async def generate_multimodal_embedding(
        self,
        text: str,
        image: ImageRef,
    ) -> list[float]:
        combined_key = f"{text}:{image.gcs_uri}"
        return self._random_vector(combined_key, self._MULTIMODAL_DIMS)

    @staticmethod
    def _random_vector(seed_text: str, dims: int) -> list[float]:
        seed = hash(seed_text) % (2**31)
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(dims)]
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector


class MockVectorIndex:
    """
    In-memory vector index. Upsert stores vectors; search returns random
    scored results from the stored items (simulates approximate nearest
    neighbour behaviour without actual distance computation).
    """

    def __init__(self) -> None:
        # {product_id: vector}
        self._vectors: dict[str, list[float]] = {}

    async def upsert(self, product_id: str, vector: list[float]) -> str:
        self._vectors[product_id] = vector
        return f"vidx_{product_id}_{uuid.uuid4().hex[:8]}"

    async def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        if not self._vectors:
            return []

        product_ids = list(self._vectors.keys())
        # Sample up to top_k items and assign descending random scores
        k = min(top_k, len(product_ids))
        selected = random.sample(product_ids, k)
        scores = sorted(
            [round(random.uniform(0.65, 0.99), 4) for _ in range(k)],
            reverse=True,
        )
        return list(zip(selected, scores))


class MockImageQuality:
    """
    Mock image quality assessor returning scores in the 0.85-0.95 range,
    representing high-quality luxury product photography.
    """

    async def assess_quality(self, images: list[ImageRef]) -> float:
        if not images:
            return 0.0
        # More images generally means a better product listing
        base = random.uniform(0.85, 0.95)
        bonus = min(len(images) * 0.01, 0.04)
        return round(min(base + bonus, 1.0), 3)
