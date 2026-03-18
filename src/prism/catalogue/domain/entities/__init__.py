"""Catalogue domain entities — Product aggregate root and Brand entity."""

from prism.catalogue.domain.entities.brand import Brand
from prism.catalogue.domain.entities.product import EnrichmentStatus, Product

__all__ = ["Brand", "EnrichmentStatus", "Product"]
