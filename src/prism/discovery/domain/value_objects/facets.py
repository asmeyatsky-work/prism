"""
Discovery Value Objects — Faceted navigation for luxury retail.

Architectural Intent:
- Facets provide structured filtering dimensions for search results
- FacetConfiguration is brand-specific — luxury brands have unique taxonomies
  (heritage, occasion, craftsmanship, material, etc.)
- All value objects are frozen dataclasses for immutability
"""

from __future__ import annotations

from dataclasses import dataclass, field

from prism.shared.domain.value_objects import ValueObject


@dataclass(frozen=True)
class FacetValue(ValueObject):
    """A single selectable value within a facet."""

    value: str = ""
    count: int = 0
    selected: bool = False


@dataclass(frozen=True)
class Facet(ValueObject):
    """
    A facet dimension for filtering search results.

    Luxury retail facets go beyond standard e-commerce (size, colour) to
    include heritage, occasion, material, craftsmanship, and designer.
    """

    name: str = ""
    display_name: str = ""
    values: tuple[FacetValue, ...] = ()

    @property
    def selected_values(self) -> tuple[FacetValue, ...]:
        return tuple(v for v in self.values if v.selected)

    @property
    def has_selection(self) -> bool:
        return any(v.selected for v in self.values)

    @property
    def total_count(self) -> int:
        return sum(v.count for v in self.values)


@dataclass(frozen=True)
class FacetConfiguration(ValueObject):
    """
    Per-brand facet configuration.

    Each luxury brand has a unique set of facet dimensions that reflect
    their product taxonomy and customer expectations. For example, a
    watchmaker may expose 'complication' and 'movement_type' facets,
    while a fashion house uses 'occasion' and 'silhouette'.
    """

    tenant_id: str = ""
    facets: tuple[FacetDefinition, ...] = ()
    default_sort: str = "relevance"
    max_facet_values: int = 50

    def get_facet_names(self) -> tuple[str, ...]:
        return tuple(f.name for f in self.facets)


@dataclass(frozen=True)
class FacetDefinition(ValueObject):
    """Definition of a single facet dimension in a brand's configuration."""

    name: str = ""
    display_name: str = ""
    field_path: str = ""
    facet_type: str = "terms"  # terms, range, hierarchy
    order: int = 0
    visible: bool = True
    luxury_attributes: tuple[str, ...] = field(default_factory=tuple)
