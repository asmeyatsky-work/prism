"""
Try-On Domain — Styling Value Objects

Architectural Intent:
- Immutable value objects for outfit composition and style recommendations
- OutfitComposition groups multiple products into a scored outfit
- StyleRecommendation carries AI-generated product suggestions with reasoning
- Supports the "Complete the Look" feature in the luxury retail experience
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.value_objects import ValueObject


@dataclass(frozen=True)
class OutfitComposition(ValueObject):
    """
    A curated outfit composed of multiple products.

    Attributes:
        items: Tuple of product IDs that form the outfit (immutable).
        style_score: AI-computed coherence score for the outfit (0.0-1.0).
        occasion: Target occasion label (e.g. "cocktail", "business", "casual_luxury").
    """

    items: tuple[str, ...] = ()
    style_score: float = 0.0
    occasion: str = ""

    def __post_init__(self) -> None:
        if not (0.0 <= self.style_score <= 1.0):
            raise ValueError(
                f"style_score must be between 0.0 and 1.0, got {self.style_score}"
            )
        if len(self.items) == 0:
            raise ValueError("OutfitComposition must contain at least one item")

    @property
    def item_count(self) -> int:
        return len(self.items)


@dataclass(frozen=True)
class StyleRecommendation(ValueObject):
    """
    AI-generated style recommendation with explainability.

    Attributes:
        recommended_product_ids: Tuple of product IDs suggested to the customer.
        reasoning: Human-readable explanation of why these products were recommended.
    """

    recommended_product_ids: tuple[str, ...] = ()
    reasoning: str = ""

    def __post_init__(self) -> None:
        if len(self.recommended_product_ids) == 0:
            raise ValueError("StyleRecommendation must include at least one product")
        if not self.reasoning:
            raise ValueError("StyleRecommendation must include reasoning")
