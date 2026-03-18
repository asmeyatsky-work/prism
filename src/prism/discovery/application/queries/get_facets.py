"""
Discovery Query — Get Facets for a search result set.

Architectural Intent:
- Returns available facets for filtering based on the current result set
- Facet computation is a read-only operation with no side effects
- Brand-specific facet configurations drive which dimensions are exposed
- Luxury retail facets include heritage, occasion, material, craftsmanship
"""

from __future__ import annotations

import logging

from prism.shared.application.dtos import QueryResult

from prism.discovery.application.dtos.search_dto import FacetDTO, FacetValueDTO
from prism.discovery.domain.value_objects.facets import (
    Facet,
    FacetConfiguration,
    FacetDefinition,
    FacetValue,
)

logger = logging.getLogger(__name__)

# Default luxury retail facet definitions used when no brand-specific
# configuration is available.
DEFAULT_LUXURY_FACETS: tuple[FacetDefinition, ...] = (
    FacetDefinition(
        name="category",
        display_name="Category",
        field_path="category",
        order=0,
    ),
    FacetDefinition(
        name="brand",
        display_name="Brand",
        field_path="brand",
        order=1,
    ),
    FacetDefinition(
        name="material",
        display_name="Material",
        field_path="attributes.material",
        order=2,
        luxury_attributes=("leather", "silk", "cashmere", "gold", "platinum"),
    ),
    FacetDefinition(
        name="occasion",
        display_name="Occasion",
        field_path="attributes.occasion",
        order=3,
        luxury_attributes=("evening", "cocktail", "resort", "bridal"),
    ),
    FacetDefinition(
        name="colour",
        display_name="Colour",
        field_path="attributes.colour",
        order=4,
    ),
    FacetDefinition(
        name="heritage",
        display_name="Heritage Collection",
        field_path="attributes.heritage",
        order=5,
        luxury_attributes=("archive", "iconic", "limited_edition"),
    ),
    FacetDefinition(
        name="price_range",
        display_name="Price Range",
        field_path="price.amount",
        facet_type="range",
        order=6,
    ),
    FacetDefinition(
        name="craftsmanship",
        display_name="Craftsmanship",
        field_path="attributes.craftsmanship",
        order=7,
        luxury_attributes=("handmade", "artisan", "bespoke"),
    ),
)


class GetFacetsQuery:
    """
    Query handler that returns available facets for a result set.

    In a full implementation, facet values and counts would be computed
    from the search engine's aggregation response. This implementation
    provides the facet structure based on brand configuration.
    """

    def __init__(
        self,
        facet_configurations: dict[str, FacetConfiguration] | None = None,
    ) -> None:
        self._configs = facet_configurations or {}

    async def execute(
        self,
        tenant_id: str,
        result_product_ids: list[str] | None = None,
        active_filters: dict[str, str | list[str]] | None = None,
    ) -> QueryResult[list[FacetDTO]]:
        """Return facets applicable for the given tenant and result set."""
        config = self._configs.get(tenant_id)

        if config is None:
            # Use default luxury facet configuration
            config = FacetConfiguration(
                tenant_id=tenant_id,
                facets=DEFAULT_LUXURY_FACETS,
            )

        facet_dtos = _build_facet_dtos(config, active_filters or {})

        return QueryResult.ok(
            data=facet_dtos,
            total_count=len(facet_dtos),
        )


def _build_facet_dtos(
    config: FacetConfiguration,
    active_filters: dict[str, str | list[str]],
) -> list[FacetDTO]:
    """
    Build FacetDTOs from configuration, marking values as selected
    based on active filters.
    """
    dtos: list[FacetDTO] = []

    # Sort facet definitions by display order
    sorted_defs = sorted(config.facets, key=lambda f: f.order)

    for defn in sorted_defs:
        if not defn.visible:
            continue

        # Determine which values are selected via active filters
        active_values = active_filters.get(defn.name, [])
        if isinstance(active_values, str):
            active_values = [active_values]

        # Build facet values — in production, counts come from search aggregation.
        # Here we provide the luxury attribute values from configuration.
        values: list[FacetValueDTO] = []
        if defn.luxury_attributes:
            for attr in defn.luxury_attributes:
                values.append(
                    FacetValueDTO(
                        value=attr,
                        count=0,  # populated by search infrastructure
                        selected=attr in active_values,
                    )
                )

        dtos.append(
            FacetDTO(
                name=defn.name,
                display_name=defn.display_name,
                values=values,
            )
        )

    return dtos
