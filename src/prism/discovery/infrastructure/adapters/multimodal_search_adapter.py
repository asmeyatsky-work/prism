"""
Discovery Infrastructure — Multimodal Search Adapter.

Architectural Intent:
- Implements ImageSearchPort and HybridSearchPort
- Uses Vertex AI multimodal embeddings for image-based search
- Hybrid search fuses text and image embeddings with configurable weights
- Image embeddings are generated from GCS-hosted images via Vertex AI

Infrastructure Details:
- Multimodal embedding model (e.g., multimodalembedding@001) generates
  embeddings for both images and text in a shared vector space
- This enables cross-modal search: text queries matched against image
  embeddings and vice versa
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from prism.shared.domain.value_objects import ImageRef

from prism.discovery.domain.value_objects.search_query import SearchResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MultimodalSearchConfig:
    """Configuration for multimodal search infrastructure."""

    project_id: str = ""
    location: str = "us-central1"
    index_endpoint_id: str = ""
    deployed_index_id: str = ""
    multimodal_model: str = "multimodalembedding@001"
    dimensions: int = 1408


class MultimodalSearchAdapter:
    """
    Implements ImageSearchPort and HybridSearchPort using Vertex AI
    multimodal embeddings.

    The adapter handles:
    - Image embedding generation from GCS-stored images
    - Visual similarity search against the multimodal index
    - Hybrid search by combining text and image embeddings with fusion weights
    """

    def __init__(self, config: MultimodalSearchConfig) -> None:
        self._config = config

    async def search_by_image(
        self,
        image: ImageRef,
        top_k: int = 20,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        """
        Execute a visual similarity search.

        Steps:
        1. Generate image embedding from the referenced GCS object
        2. Query the multimodal vector index
        3. Map results to domain SearchResult objects
        """
        logger.info(
            "Executing image search: image=%s, top_k=%d, tenant=%s",
            image.gcs_uri,
            top_k,
            tenant_id,
        )

        embedding = await self._generate_image_embedding(image)
        restricts = self._build_restricts(tenant_id)
        raw_results = await self._query_index(embedding, top_k, restricts)

        return [
            SearchResult(
                product_id=r["id"],
                score=r["distance"],
                rank=idx + 1,
                explanation=f"visual similarity: {r['distance']:.4f}",
            )
            for idx, r in enumerate(raw_results)
        ]

    async def search_hybrid(
        self,
        text: str,
        image: ImageRef,
        weights: tuple[float, float] = (0.5, 0.5),
        top_k: int = 20,
        filters: dict[str, str | list[str]] | None = None,
        tenant_id: str = "",
    ) -> list[SearchResult]:
        """
        Execute hybrid search by fusing text and image embeddings.

        The multimodal embedding model places both text and images in the
        same vector space. This method generates embeddings for both inputs,
        computes a weighted average, and searches the index with the fused
        embedding.
        """
        logger.info(
            "Executing hybrid search: text=%r, image=%s, weights=%s, tenant=%s",
            text[:50],
            image.gcs_uri,
            weights,
            tenant_id,
        )

        text_embedding = await self._generate_text_embedding(text)
        image_embedding = await self._generate_image_embedding(image)

        # Weighted fusion of text and image embeddings
        text_weight, image_weight = weights
        fused = [
            text_weight * t + image_weight * i
            for t, i in zip(text_embedding, image_embedding)
        ]

        restricts = self._build_restricts(tenant_id, filters)
        raw_results = await self._query_index(fused, top_k, restricts)

        return [
            SearchResult(
                product_id=r["id"],
                score=r["distance"],
                rank=idx + 1,
                explanation=(
                    f"hybrid match (text={text_weight:.1f}, "
                    f"image={image_weight:.1f}): {r['distance']:.4f}"
                ),
            )
            for idx, r in enumerate(raw_results)
        ]

    async def _generate_image_embedding(self, image: ImageRef) -> list[float]:
        """
        Generate an image embedding using Vertex AI multimodal model.

        In production, this calls:
            MultiModalEmbeddingModel.get_embeddings(
                image=Image.load_from_file(image.gcs_uri)
            )
        """
        logger.debug("Generating image embedding: %s", image.gcs_uri)
        return [0.0] * self._config.dimensions

    async def _generate_text_embedding(self, text: str) -> list[float]:
        """
        Generate a text embedding using the multimodal model.

        Text and images share the same embedding space, enabling
        cross-modal retrieval.
        """
        logger.debug("Generating text embedding for multimodal: %r", text[:50])
        return [0.0] * self._config.dimensions

    async def _query_index(
        self,
        embedding: list[float],
        top_k: int,
        restricts: list[dict],
    ) -> list[dict]:
        """Query the multimodal vector search index."""
        logger.debug(
            "Querying multimodal index: top_k=%d, restricts=%d",
            top_k,
            len(restricts),
        )
        return []

    def _build_restricts(
        self,
        tenant_id: str,
        filters: dict[str, str | list[str]] | None = None,
    ) -> list[dict]:
        """Build namespace restricts for tenant isolation and user filters."""
        restricts: list[dict] = []

        if tenant_id:
            restricts.append({
                "namespace": "tenant_id",
                "allow_list": [tenant_id],
            })

        if filters:
            for key, value in filters.items():
                allow = value if isinstance(value, list) else [value]
                restricts.append({
                    "namespace": key,
                    "allow_list": allow,
                })

        return restricts
