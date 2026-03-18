"""
Discovery Context — Mock Search Adapters

Provides mock implementations of:
- VectorSearchPort       -> MockVectorSearch
- ImageSearchPort        -> MockImageSearch
- HybridSearchPort       -> MockHybridSearch
- PersonalisationPort    -> MockPersonalisation

MockVectorSearch maintains an in-memory product store and performs text
substring matching. MockImageSearch returns random products as results.
MockPersonalisation returns static luxury shopper re-ranking signals.
"""

from __future__ import annotations

import random

from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchResult,
)
from prism.shared.domain.value_objects import ImageRef


# ── Seed product catalogue for search results ──────────────────────────

_DEMO_PRODUCTS: list[dict[str, str]] = [
    {
        "id": "prod_gucci_diana_001",
        "name": "Gucci Diana Mini Tote Bag",
        "category": "handbags",
        "brand": "Gucci",
    },
    {
        "id": "prod_gucci_horsebit_002",
        "name": "Gucci Horsebit 1955 Shoulder Bag",
        "category": "handbags",
        "brand": "Gucci",
    },
    {
        "id": "prod_lv_capucines_003",
        "name": "Louis Vuitton Capucines MM",
        "category": "handbags",
        "brand": "Louis Vuitton",
    },
    {
        "id": "prod_hermes_birkin_004",
        "name": "Hermès Birkin 30 Togo Leather",
        "category": "handbags",
        "brand": "Hermès",
    },
    {
        "id": "prod_dior_saddle_005",
        "name": "Dior Saddle Bag in Oblique Jacquard",
        "category": "handbags",
        "brand": "Dior",
    },
    {
        "id": "prod_bottega_cassette_006",
        "name": "Bottega Veneta Cassette Bag in Intrecciato",
        "category": "handbags",
        "brand": "Bottega Veneta",
    },
    {
        "id": "prod_chanel_classic_007",
        "name": "Chanel Classic Flap Bag Medium",
        "category": "handbags",
        "brand": "Chanel",
    },
    {
        "id": "prod_prada_galleria_008",
        "name": "Prada Galleria Saffiano Leather Bag",
        "category": "handbags",
        "brand": "Prada",
    },
    {
        "id": "prod_gucci_ace_009",
        "name": "Gucci Ace Embroidered Sneaker",
        "category": "shoes",
        "brand": "Gucci",
    },
    {
        "id": "prod_lv_archlight_010",
        "name": "Louis Vuitton Archlight Sneaker",
        "category": "shoes",
        "brand": "Louis Vuitton",
    },
    {
        "id": "prod_louboutin_kate_011",
        "name": "Christian Louboutin Kate 100 Patent Pump",
        "category": "shoes",
        "brand": "Christian Louboutin",
    },
    {
        "id": "prod_gucci_flora_012",
        "name": "Gucci Flora Print Silk Dress",
        "category": "dresses",
        "brand": "Gucci",
    },
    {
        "id": "prod_valentino_gown_013",
        "name": "Valentino Garavani Cady Couture Evening Gown",
        "category": "dresses",
        "brand": "Valentino",
    },
    {
        "id": "prod_burberry_trench_014",
        "name": "Burberry Heritage Kensington Trench Coat",
        "category": "outerwear",
        "brand": "Burberry",
    },
    {
        "id": "prod_maxmara_teddy_015",
        "name": "Max Mara Teddy Bear Icon Coat",
        "category": "outerwear",
        "brand": "Max Mara",
    },
    {
        "id": "prod_cartier_tank_016",
        "name": "Cartier Tank Française Watch",
        "category": "watches",
        "brand": "Cartier",
    },
    {
        "id": "prod_rolex_datejust_017",
        "name": "Rolex Datejust 36 Oyster Steel",
        "category": "watches",
        "brand": "Rolex",
    },
    {
        "id": "prod_hermes_carre_018",
        "name": "Hermès Carré 90 Silk Scarf",
        "category": "accessories",
        "brand": "Hermès",
    },
    {
        "id": "prod_celine_triomphe_019",
        "name": "Celine Triomphe Belt in Smooth Calfskin",
        "category": "accessories",
        "brand": "Celine",
    },
    {
        "id": "prod_tiffany_pendant_020",
        "name": "Tiffany & Co. Elsa Peretti Open Heart Pendant",
        "category": "jewellery",
        "brand": "Tiffany & Co.",
    },
]

_EXPLANATIONS = [
    "Strong semantic match on material and silhouette attributes",
    "Visual similarity score boosted by colour palette alignment",
    "High relevance: query terms match product category and brand positioning",
    "Cross-category recommendation based on occasion and style profile",
    "Personalisation boost from browsing history affinity",
    "Brand-level relevance amplified by seasonal collection alignment",
]


class MockVectorSearch:
    """
    In-memory text search that performs case-insensitive substring matching
    against a seeded luxury product catalogue, returning SearchResult objects
    with relevance scores.
    """

    def __init__(self, products: list[dict[str, str]] | None = None) -> None:
        self._products = products or list(_DEMO_PRODUCTS)

    async def search_by_text(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        query_lower = query.lower()
        tokens = query_lower.split()

        scored: list[tuple[dict[str, str], float]] = []
        for product in self._products:
            searchable = (
                f"{product['name']} {product['category']} {product['brand']}"
            ).lower()

            # Score based on token hit ratio
            hits = sum(1 for token in tokens if token in searchable)
            if hits == 0:
                continue
            base_score = hits / len(tokens)
            # Add a small random perturbation for realistic ordering
            score = round(base_score * 0.6 + random.uniform(0.2, 0.4), 4)
            scored.append((product, min(score, 1.0)))

        # Apply filters
        if filters:
            category_filter = filters.get("category")
            brand_filter = filters.get("brand")
            filtered = []
            for prod, sc in scored:
                if category_filter:
                    cats = [category_filter] if isinstance(category_filter, str) else category_filter
                    if prod["category"] not in cats:
                        continue
                if brand_filter:
                    brands = [brand_filter] if isinstance(brand_filter, str) else brand_filter
                    if prod["brand"] not in brands:
                        continue
                filtered.append((prod, sc))
            scored = filtered

        # Sort descending by score
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]

        results: list[SearchResult] = []
        for rank, (product, score) in enumerate(scored, start=1):
            results.append(
                SearchResult(
                    product_id=product["id"],
                    score=score,
                    rank=rank,
                    explanation=random.choice(_EXPLANATIONS),
                )
            )
        return results


class MockImageSearch:
    """
    Mock image search that returns random products from the demo catalogue
    as visual similarity results. Simulates what a real image embedding
    search would return.
    """

    def __init__(self, products: list[dict[str, str]] | None = None) -> None:
        self._products = products or list(_DEMO_PRODUCTS)

    async def search_by_image(
        self,
        image: ImageRef,
        top_k: int = 20,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        k = min(top_k, len(self._products))
        selected = random.sample(self._products, k)
        scores = sorted(
            [round(random.uniform(0.60, 0.95), 4) for _ in range(k)],
            reverse=True,
        )
        return [
            SearchResult(
                product_id=prod["id"],
                score=score,
                rank=rank,
                explanation="Visual similarity match based on shape, texture, and colour analysis",
            )
            for rank, (prod, score) in enumerate(zip(selected, scores), start=1)
        ]


class MockHybridSearch:
    """
    Combines text and image search with configurable fusion weights.
    In practice, text results are generated from substring matching
    and combined with random-scored visual results.
    """

    def __init__(self) -> None:
        self._text_search = MockVectorSearch()
        self._image_search = MockImageSearch()

    async def search_hybrid(
        self,
        text: str,
        image: ImageRef,
        weights: tuple[float, float] = (0.5, 0.5),
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        text_weight, image_weight = weights

        text_results = await self._text_search.search_by_text(
            text, top_k=top_k * 2, filters=filters, tenant_id=tenant_id
        )
        image_results = await self._image_search.search_by_image(
            image, top_k=top_k * 2, tenant_id=tenant_id
        )

        # Fuse scores by product_id
        score_map: dict[str, float] = {}
        for r in text_results:
            score_map[r.product_id] = score_map.get(r.product_id, 0.0) + r.score * text_weight
        for r in image_results:
            score_map[r.product_id] = score_map.get(r.product_id, 0.0) + r.score * image_weight

        # Sort and build results
        sorted_items = sorted(score_map.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            SearchResult(
                product_id=pid,
                score=round(score, 4),
                rank=rank,
                explanation="Hybrid fusion of semantic text match and visual similarity",
            )
            for rank, (pid, score) in enumerate(sorted_items, start=1)
        ]


class MockPersonalisation:
    """
    Returns static re-ranking signals representing a luxury shopper profile.
    Simulates a high-value returning customer with strong brand affinities.
    """

    async def get_signals(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> ReRankingSignals:
        return ReRankingSignals(
            browsing_history=(
                "prod_gucci_diana_001",
                "prod_hermes_birkin_004",
                "prod_chanel_classic_007",
                "prod_bottega_cassette_006",
                "prod_cartier_tank_016",
            ),
            purchase_history=(
                "prod_gucci_horsebit_002",
                "prod_burberry_trench_014",
                "prod_hermes_carre_018",
            ),
            preferences={
                "preferred_materials": ["leather", "silk", "cashmere"],
                "preferred_colours": ["Nero", "Burgundy", "Camel"],
                "preferred_brands": ["Gucci", "Hermès", "Bottega Veneta"],
                "avoided_materials": ["synthetic"],
                "price_tier": "ultra-premium",
                "style_profile": "timeless elegance",
            },
        )
