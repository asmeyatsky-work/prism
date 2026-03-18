"""
Discovery Domain Ports — Protocol-based interfaces for search infrastructure.

Architectural Intent:
- Ports define the contracts that infrastructure adapters must fulfil
- Using Protocol (structural subtyping) keeps the domain layer free of
  framework dependencies
- Each port represents a distinct infrastructure capability:
  * VectorSearchPort — text-based semantic search via embeddings
  * ImageSearchPort — visual similarity search
  * HybridSearchPort — fused text + image search
  * PersonalisationPort — customer signal retrieval for re-ranking
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from prism.shared.domain.value_objects import ImageRef

from prism.discovery.domain.value_objects.search_query import (
    ReRankingSignals,
    SearchResult,
)


@runtime_checkable
class VectorSearchPort(Protocol):
    """
    Port for text-based vector similarity search.

    Implementations use embedding models to convert text queries into
    vectors and perform approximate nearest-neighbour search against
    a product embedding index.
    """

    async def search_by_text(
        self,
        query: str,
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]: ...


@runtime_checkable
class ImageSearchPort(Protocol):
    """
    Port for image-based visual similarity search.

    Implementations extract visual embeddings from a reference image
    and search for visually similar products in the index.
    """

    async def search_by_image(
        self,
        image: ImageRef,
        top_k: int = 20,
        tenant_id: str = "",
    ) -> list[SearchResult]: ...


@runtime_checkable
class HybridSearchPort(Protocol):
    """
    Port for hybrid (text + image) search with configurable fusion weights.

    Hybrid search is the primary modality for luxury retail — customers
    often combine a reference image with textual refinements.
    """

    async def search_hybrid(
        self,
        text: str,
        image: ImageRef,
        weights: tuple[float, float] = (0.5, 0.5),
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]: ...


@runtime_checkable
class PersonalisationPort(Protocol):
    """
    Port for retrieving customer personalisation signals.

    Signals include browsing history, purchase history, and explicit
    preferences. Used by the ranking service for re-ranking.
    """

    async def get_signals(
        self,
        customer_id: str,
        tenant_id: str,
    ) -> ReRankingSignals: ...
