"""
Quality Scoring Domain Service

Architectural Intent:
- Stateless domain service that computes product data quality scores
- Score components: attribute completeness, image presence, description richness
- Pure business logic — no infrastructure dependencies
- Used by the enrichment pipeline to assess improvement and by dashboards
  to track catalogue health over time

Scoring Model:
- Completeness (40%): Fraction of key attributes that are populated
- Image quality (30%): Number and presence of product images
- Description richness (30%): Length and presence of editorial description

All weights are tunable but default to luxury retail best practices.
"""

from __future__ import annotations

from prism.catalogue.domain.entities.product import Product


# Key attributes expected for a fully-enriched luxury product
_KEY_ATTRIBUTES = (
    "material",
    "colour",
    "pattern",
    "silhouette",
    "occasion",
    "season",
    "style_tags",
    "fit",
    "care_instructions",
    "country_of_origin",
)

# Scoring weights
_WEIGHT_COMPLETENESS = 0.40
_WEIGHT_IMAGES = 0.30
_WEIGHT_DESCRIPTION = 0.30

# Thresholds
_IDEAL_IMAGE_COUNT = 4
_IDEAL_DESCRIPTION_LENGTH = 200  # characters


class QualityService:
    """
    Domain service for computing product data quality scores.

    Evaluates a Product aggregate across three dimensions:
    1. Attribute completeness — how many key luxury product attributes are populated
    2. Image coverage — whether the product has sufficient visual assets
    3. Description richness — whether the editorial description meets length thresholds

    The resulting score (0.0 to 1.0) represents overall catalogue readiness.
    """

    def calculate_quality_score(self, product: Product) -> float:
        """
        Compute a quality score for the given product.

        The score is a weighted combination of completeness, image quality,
        and description richness, normalised to the 0.0 - 1.0 range.

        Args:
            product: The Product aggregate to evaluate.

        Returns:
            A float between 0.0 and 1.0 representing catalogue readiness.
        """
        completeness = self._score_completeness(product)
        images = self._score_images(product)
        description = self._score_description(product)

        raw_score = (
            _WEIGHT_COMPLETENESS * completeness
            + _WEIGHT_IMAGES * images
            + _WEIGHT_DESCRIPTION * description
        )

        # Clamp to [0.0, 1.0] for safety
        return round(max(0.0, min(1.0, raw_score)), 4)

    def _score_completeness(self, product: Product) -> float:
        """
        Score attribute completeness against key luxury product attributes.

        Checks both top-level product fields (category, subcategory) and
        entries in the attributes dict.

        Returns:
            Float between 0.0 and 1.0.
        """
        if not _KEY_ATTRIBUTES:
            return 1.0

        populated_count = 0
        for attr_name in _KEY_ATTRIBUTES:
            # Check in the attributes dict first
            if attr_name in product.attributes and product.attributes[attr_name]:
                populated_count += 1
                continue
            # Check top-level fields
            value = getattr(product, attr_name, None)
            if value:
                populated_count += 1

        return populated_count / len(_KEY_ATTRIBUTES)

    def _score_images(self, product: Product) -> float:
        """
        Score image coverage.

        A product with zero images scores 0.0. The score scales linearly
        up to the ideal image count, where it reaches 1.0.

        Returns:
            Float between 0.0 and 1.0.
        """
        if not product.images:
            return 0.0
        return min(1.0, len(product.images) / _IDEAL_IMAGE_COUNT)

    def _score_description(self, product: Product) -> float:
        """
        Score editorial description richness.

        Evaluates the product name and description. A missing description
        severely penalises the score. Length is measured against the
        ideal threshold for luxury product descriptions.

        Returns:
            Float between 0.0 and 1.0.
        """
        score = 0.0

        # Name presence (20% of description score)
        if product.name:
            score += 0.2

        # Description presence and length (80% of description score)
        if product.description:
            length_ratio = min(1.0, len(product.description) / _IDEAL_DESCRIPTION_LENGTH)
            score += 0.8 * length_ratio

        return score
