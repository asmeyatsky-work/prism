"""
Catalogue Context — In-Memory Mock Adapters

Provides mock implementations of:
- ProductRepositoryPort  -> InMemoryProductRepository
- BrandRepositoryPort    -> InMemoryBrandRepository
- CatalogueEnrichmentPort -> MockCatalogueEnrichmentPort
- EmbeddingPort          -> MockEmbeddingPort

All storage is dict-based and tenant-scoped. Search uses substring matching
against product name and description fields.
"""

from __future__ import annotations

import random
import uuid
from typing import Any

from prism.catalogue.domain.entities.brand import Brand
from prism.catalogue.domain.entities.product import Product
from prism.shared.domain.value_objects import TenantId


class InMemoryProductRepository:
    """
    In-memory product repository with tenant-scoped dict storage.

    Products are keyed by (tenant_id, product_id) for isolation.
    Search performs case-insensitive substring matching on name and description.
    """

    def __init__(self) -> None:
        # {tenant_id_value: {product_id: Product}}
        self._store: dict[str, dict[str, Product]] = {}

    async def get_by_id(self, product_id: str, tenant_id: TenantId) -> Product | None:
        tenant_store = self._store.get(tenant_id.value, {})
        return tenant_store.get(product_id)

    async def get_by_sku(self, sku: str, tenant_id: TenantId) -> Product | None:
        tenant_store = self._store.get(tenant_id.value, {})
        for product in tenant_store.values():
            if product.sku == sku:
                return product
        return None

    async def save(self, product: Product) -> None:
        tid = product.tenant_id.value
        if tid not in self._store:
            self._store[tid] = {}
        self._store[tid][product.id] = product

    async def list_by_tenant(
        self,
        tenant_id: TenantId,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        tenant_store = self._store.get(tenant_id.value, {})
        all_products = list(tenant_store.values())
        total = len(all_products)
        page = all_products[offset : offset + limit]
        return page, total

    async def search(
        self,
        tenant_id: TenantId,
        query: str,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Product], int]:
        tenant_store = self._store.get(tenant_id.value, {})
        query_lower = query.lower()
        matches = [
            p
            for p in tenant_store.values()
            if query_lower in p.name.lower()
            or query_lower in p.description.lower()
            or query_lower in p.category.lower()
            or query_lower in p.brand.lower()
        ]
        total = len(matches)
        page = matches[offset : offset + limit]
        return page, total

    # --- Demo convenience methods (not part of the domain port) ---

    def count_all(self) -> int:
        """Count all products across all tenants."""
        return sum(len(store) for store in self._store.values())

    def get_by_id_any_tenant(self, product_id: str) -> Product | None:
        """Look up a product by ID across all tenants (demo convenience)."""
        for tenant_store in self._store.values():
            if product_id in tenant_store:
                return tenant_store[product_id]
        return None


class InMemoryBrandRepository:
    """
    In-memory brand repository with tenant-scoped storage.
    """

    def __init__(self) -> None:
        # {tenant_id_value: {brand_id: Brand}}
        self._store: dict[str, dict[str, Brand]] = {}

    async def get_by_id(self, brand_id: str, tenant_id: TenantId) -> Brand | None:
        tenant_store = self._store.get(tenant_id.value, {})
        return tenant_store.get(brand_id)

    async def save(self, brand: Brand) -> None:
        tid = brand.tenant_id.value
        if tid not in self._store:
            self._store[tid] = {}
        self._store[tid][brand.id] = brand

    async def list_all(self, tenant_id: TenantId) -> list[Brand]:
        tenant_store = self._store.get(tenant_id.value, {})
        return list(tenant_store.values())


# ── Enrichment attribute pools for realistic mock data ──────────────────

_LUXURY_MATERIALS = [
    "Italian calfskin leather",
    "Nappa lambskin",
    "Japanese silk twill",
    "Virgin merino wool",
    "Cashmere double-face",
    "Saffiano leather",
    "Epi leather",
    "Canvas with leather trim",
    "Duchesse satin",
    "Alcantara suede",
    "Crocodile-embossed leather",
    "Organza",
]

_LUXURY_COLOURS = [
    "Nero",
    "Ivory",
    "Burgundy",
    "Midnight Navy",
    "Champagne Gold",
    "Dusty Rose",
    "Emerald",
    "Camel",
    "Slate Grey",
    "Powder Blue",
    "Cognac",
    "Obsidian",
]

_PATTERNS = [
    "Solid",
    "Monogram jacquard",
    "Houndstooth",
    "GG Supreme",
    "Damier",
    "Intrecciato woven",
    "Floral embroidered",
    "Prince of Wales check",
    "Abstract geometric",
    "Tonal stripe",
]

_SILHOUETTES = [
    "Structured",
    "Relaxed",
    "A-line",
    "Oversized",
    "Tailored slim",
    "Boxy cropped",
    "Draped",
    "Hourglass",
    "Column",
    "Trapeze",
]

_OCCASIONS = [
    "Black-tie evening",
    "Business formal",
    "Resort casual",
    "Weekend brunch",
    "Gallery opening",
    "Cocktail reception",
    "Travel",
    "Après-ski",
]

_SEASONS = ["SS25", "AW25", "Resort 2025", "Pre-Fall 2025", "Cruise 2026"]

_HARDWARE_FINISHES = [
    "Palladium",
    "Light gold",
    "Ruthenium",
    "Antique brass",
    "Silver-tone",
    "Rose gold",
]


class MockCatalogueEnrichmentPort:
    """
    Mock AI enrichment that returns realistic luxury product attributes
    and editorial descriptions based on product context.
    """

    async def extract_attributes(self, product: Product) -> dict[str, str]:
        category_lower = (product.category or "").lower()

        attrs: dict[str, str] = {
            "material": random.choice(_LUXURY_MATERIALS),
            "colour": random.choice(_LUXURY_COLOURS),
            "pattern": random.choice(_PATTERNS),
            "silhouette": random.choice(_SILHOUETTES),
            "occasion": random.choice(_OCCASIONS),
            "season": random.choice(_SEASONS),
            "country_of_origin": random.choice(["Italy", "France", "Spain", "United Kingdom"]),
            "care_instructions": "Professional dry clean only",
        }

        # Category-specific attributes
        if "bag" in category_lower or "handbag" in category_lower:
            attrs.update({
                "hardware": random.choice(_HARDWARE_FINISHES),
                "closure_type": random.choice(["Magnetic snap", "Turn-lock", "Zip-top", "Drawstring"]),
                "lining": random.choice(["Suede", "Microfibre", "Cotton twill", "Silk"]),
                "dimensions": f"{random.randint(20, 40)}cm x {random.randint(12, 28)}cm x {random.randint(6, 15)}cm",
                "strap_drop": f"{random.randint(18, 55)}cm",
            })
        elif "shoe" in category_lower or "boot" in category_lower:
            attrs.update({
                "heel_height": f"{random.choice([2, 4, 6, 8, 10, 12])}cm",
                "sole": random.choice(["Leather sole", "Rubber sole", "Commando sole"]),
                "toe_shape": random.choice(["Pointed", "Almond", "Round", "Square"]),
            })
        elif "watch" in category_lower:
            attrs.update({
                "movement": random.choice(["Swiss automatic", "Quartz", "Manual winding"]),
                "case_diameter": f"{random.choice([36, 38, 40, 42, 44])}mm",
                "water_resistance": random.choice(["30m", "50m", "100m", "300m"]),
            })

        return attrs

    async def generate_description(self, product: Product, tone: str) -> str:
        tone_lower = tone.lower()
        name = product.name or "this exquisite piece"
        brand = product.brand or "the Maison"
        material = product.attributes.get("material", "the finest materials")

        if "luxury" in tone_lower or "sophisticated" in tone_lower:
            templates = [
                (
                    f"Crafted with uncompromising attention to detail, the {name} "
                    f"by {brand} embodies the very essence of modern luxury. "
                    f"Realised in {material}, this piece speaks to a refined "
                    f"sensibility that transcends seasons, offering an enduring "
                    f"silhouette that moves effortlessly from day to evening."
                ),
                (
                    f"A testament to {brand}'s heritage of excellence, the {name} "
                    f"is meticulously constructed from {material}, selected for its "
                    f"exceptional drape and hand-feel. Every stitch reflects the "
                    f"Maison's commitment to artisanal savoir-faire, resulting in "
                    f"a piece of timeless elegance."
                ),
                (
                    f"The {name} exemplifies {brand}'s mastery of proportion and "
                    f"material. Fashioned from {material} by skilled artisans in "
                    f"the Maison's atelier, it offers a harmonious balance of "
                    f"structure and fluidity that defines contemporary luxury."
                ),
            ]
        elif "contemporary" in tone_lower or "minimal" in tone_lower:
            templates = [
                (
                    f"The {name}. Clean lines. Impeccable {material}. "
                    f"{brand} strips away the unnecessary, leaving only what "
                    f"matters: form, fabric, and a silhouette that speaks for itself."
                ),
                (
                    f"{brand} presents the {name} -- a study in restraint and "
                    f"precision. Crafted from {material}, it pairs effortlessly "
                    f"with the modern wardrobe's demand for versatile, "
                    f"understated refinement."
                ),
            ]
        elif "avant-garde" in tone_lower or "edgy" in tone_lower:
            templates = [
                (
                    f"Deconstructed. Reimagined. The {name} challenges convention "
                    f"with {brand}'s signature irreverence. {material.capitalize()} "
                    f"is transformed through experimental techniques into something "
                    f"entirely new -- a provocation dressed as a garment."
                ),
                (
                    f"From {brand}'s boundary-pushing atelier, the {name} "
                    f"subverts expectation. Raw edges meet {material} in an "
                    f"unapologetic statement of creative audacity that refuses "
                    f"to be categorised."
                ),
            ]
        else:
            templates = [
                (
                    f"Introducing the {name} by {brand} -- a versatile "
                    f"addition to any discerning wardrobe. Crafted from "
                    f"{material}, it offers both comfort and sophistication "
                    f"for the modern connoisseur."
                ),
            ]

        return random.choice(templates)


class MockEmbeddingPort:
    """
    Mock embedding port that generates random 768-dimensional vectors
    and stores them in an in-memory dictionary.
    """

    _DIMENSIONS = 768

    def __init__(self) -> None:
        # {product_id: vector}
        self._index: dict[str, list[float]] = {}

    async def generate_embedding(self, product: Product) -> list[float]:
        # Generate a deterministic-ish random vector seeded by product name
        seed = hash(product.name + product.sku) % (2**31)
        rng = random.Random(seed)
        vector = [rng.gauss(0, 1) for _ in range(self._DIMENSIONS)]
        # Normalize
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        return vector

    async def index_embedding(self, product_id: str, vector: list[float]) -> str:
        vector_id = f"vec_{product_id}_{uuid.uuid4().hex[:8]}"
        self._index[product_id] = vector
        return vector_id
