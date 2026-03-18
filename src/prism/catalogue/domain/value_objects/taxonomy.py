"""
Catalogue Value Objects — Taxonomy and Product Attributes

Architectural Intent:
- TaxonomyCode bridges GS1 standard codes with PRISM's internal taxonomy
- Confidence score tracks AI-assigned taxonomy reliability
- ProductCategory and ProductAttribute are strongly typed to prevent
  stringly-typed attribute soup in the product aggregate
- All value objects are frozen dataclasses — equality is structural
"""

from __future__ import annotations

from dataclasses import dataclass

from prism.shared.domain.value_objects import ValueObject


@dataclass(frozen=True)
class TaxonomyCode(ValueObject):
    """
    Dual taxonomy code mapping GS1 to PRISM's internal classification.

    GS1 codes provide industry-standard product classification. PRISM codes
    add luxury-specific granularity (e.g., distinguishing haute couture from
    ready-to-wear within the same GS1 category).

    Attributes:
        gs1_code: GS1 Global Product Classification code (e.g. "10000043").
        prism_code: PRISM internal taxonomy code (e.g. "LUX.RTW.DRESS.EVENING").
        confidence: AI-assigned confidence in the mapping (0.0 to 1.0).
    """

    gs1_code: str
    prism_code: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.gs1_code:
            raise ValueError("GS1 code cannot be empty")
        if not self.prism_code:
            raise ValueError("PRISM code cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )


@dataclass(frozen=True)
class ProductCategory(ValueObject):
    """
    Hierarchical product category within the PRISM taxonomy.

    Supports up to three levels of nesting for luxury retail categorisation:
    category -> subcategory -> segment (e.g., Clothing -> Dresses -> Evening).

    Attributes:
        name: Display name of the category.
        code: Machine-readable category code.
        parent_code: Code of the parent category, empty for top-level categories.
        level: Depth in the hierarchy (0 = top level).
    """

    name: str
    code: str
    parent_code: str = ""
    level: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Category name cannot be empty")
        if not self.code:
            raise ValueError("Category code cannot be empty")
        if self.level < 0:
            raise ValueError(f"Category level must be non-negative, got {self.level}")


@dataclass(frozen=True)
class ProductAttribute(ValueObject):
    """
    A single product attribute with its value and provenance.

    Tracks whether an attribute was extracted by AI or entered manually,
    along with the confidence of AI-extracted values.

    Attributes:
        name: Attribute key (e.g. "material", "colour", "pattern").
        value: Attribute value (e.g. "cashmere", "midnight blue", "herringbone").
        source: Origin of the attribute value — "ai", "manual", or "ucp".
        confidence: Confidence score for AI-extracted attributes (0.0 to 1.0).
    """

    name: str
    value: str
    source: str = "manual"
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Attribute name cannot be empty")
        if self.source not in ("ai", "manual", "ucp"):
            raise ValueError(
                f"Attribute source must be 'ai', 'manual', or 'ucp', got '{self.source}'"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"Confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
