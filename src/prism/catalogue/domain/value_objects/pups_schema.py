"""
PRISM Unified Product Schema (PUPS)

Architectural Intent:
- Canonical structured representation of an enriched luxury product
- Pydantic model for use as structured AI output schema (Gemini, Claude)
- Fields align with the PRD product attribute taxonomy for luxury retail
- Used by the enrichment pipeline to produce typed, validated output
- Serves as the contract between Catalogue and downstream consumers
  (Discovery for search facets, Try-On for garment metadata, Intelligence for analytics)

Design Notes:
- Optional fields allow partial enrichment — products progress through RAW -> ENRICHED
- Tuple types for multi-valued attributes (a product can have multiple materials)
- style_tags are free-form for AI-generated luxury taxonomy extensions
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PUPSRecord(BaseModel):
    """
    The PRISM Unified Product Schema — full enriched product record.

    This is the structured output target for AI enrichment pipelines.
    Each field maps to a facet in the luxury retail product taxonomy
    defined in the PRISM PRD.
    """

    # Core identification
    sku: str = Field(..., description="Stock Keeping Unit — unique product identifier")
    name: str = Field(..., description="Product display name")
    brand: str = Field(..., description="Brand name")

    # Descriptive content
    short_description: str = Field(
        default="",
        description="Brief product summary (1-2 sentences) for cards and previews",
    )
    long_description: str = Field(
        default="",
        description="Full editorial product description in brand voice",
    )

    # Material and construction
    material: tuple[str, ...] = Field(
        default=(),
        description="Primary materials (e.g. 'cashmere', 'silk twill', 'lambskin')",
    )
    material_composition: str = Field(
        default="",
        description="Detailed composition (e.g. '70% cashmere, 30% silk')",
    )

    # Visual attributes
    colour: str = Field(
        default="",
        description="Primary colour name (e.g. 'midnight blue', 'ivory')",
    )
    colour_family: str = Field(
        default="",
        description="Normalised colour family for faceted search (e.g. 'blue', 'white')",
    )
    pattern: str = Field(
        default="",
        description="Pattern type (e.g. 'herringbone', 'floral', 'solid')",
    )

    # Shape and fit
    silhouette: str = Field(
        default="",
        description="Garment silhouette (e.g. 'A-line', 'fitted', 'oversized')",
    )
    fit: str = Field(
        default="",
        description="Fit descriptor (e.g. 'slim', 'regular', 'relaxed')",
    )

    # Occasion and season
    occasion: tuple[str, ...] = Field(
        default=(),
        description="Suitable occasions (e.g. 'evening', 'casual', 'business')",
    )
    season: tuple[str, ...] = Field(
        default=(),
        description="Applicable seasons (e.g. 'SS25', 'AW25', 'resort')",
    )

    # Style classification
    style_tags: tuple[str, ...] = Field(
        default=(),
        description="AI-generated style tags for discovery and recommendation",
    )

    # Category
    category: str = Field(
        default="",
        description="Top-level product category (e.g. 'Clothing', 'Accessories')",
    )
    subcategory: str = Field(
        default="",
        description="Subcategory (e.g. 'Dresses', 'Handbags', 'Scarves')",
    )

    # Sizing and dimensions
    size_system: str = Field(
        default="",
        description="Size system (e.g. 'EU', 'US', 'UK', 'IT')",
    )
    available_sizes: tuple[str, ...] = Field(
        default=(),
        description="Available sizes in the product's size system",
    )

    # Care
    care_instructions: tuple[str, ...] = Field(
        default=(),
        description="Care instructions (e.g. 'dry clean only', 'hand wash')",
    )

    # Provenance
    country_of_origin: str = Field(
        default="",
        description="Country of manufacture (e.g. 'Italy', 'France')",
    )

    model_config = {"frozen": True}
