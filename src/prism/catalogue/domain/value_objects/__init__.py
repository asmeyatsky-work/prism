"""Catalogue value objects — taxonomy codes, product attributes, and PUPS schema."""

from prism.catalogue.domain.value_objects.pups_schema import PUPSRecord
from prism.catalogue.domain.value_objects.taxonomy import (
    ProductAttribute,
    ProductCategory,
    TaxonomyCode,
)

__all__ = [
    "PUPSRecord",
    "ProductAttribute",
    "ProductCategory",
    "TaxonomyCode",
]
