"""Catalogue domain ports — protocol-based interfaces for infrastructure adapters."""

from prism.catalogue.domain.ports.enrichment_ports import (
    CatalogueEnrichmentPort,
    EmbeddingPort,
)
from prism.catalogue.domain.ports.repository_ports import (
    BrandRepositoryPort,
    ProductRepositoryPort,
)

__all__ = [
    "BrandRepositoryPort",
    "CatalogueEnrichmentPort",
    "EmbeddingPort",
    "ProductRepositoryPort",
]
